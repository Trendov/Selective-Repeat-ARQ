import sys, socket, re, os, time, random, pickle, signal
Packsize=1440
Timeout=0.002#starting timeout
window_size=250#starting window_size

def GetArguments(): # this function checks the arguments and return them to main code
    if (len(sys.argv)!=2):#if we dont put 2 arguments it exits
        sys.exit()
    IpPort= sys.argv[1]#first arg is IP and Port
    IpPort=IpPort.split(":")#splitting IP and Port
    IP=IpPort[0]#first is IP
    Port=IpPort[1]#second is Port number
    try:
        Port=int(Port)
    except:
        sys.exit()
    if ((Port <1025) or (Port>65535)):#Port should be between this two numbers not to interfere
        sys.exit()
    IPWrong=False#flag for IP(to exit or not)
    IPSplit=IP.split(".")#splitting the IP
    for Num in IPSplit:
        try:
            Num=int(Num)
        except:
            sys.exit()
        if (Num > 255) :
            IPWrong=True
    if IPWrong:
        sys.exit()
    return IP, Port

def signal_handler(sig, frame):#For Ctrl+C
    sys.exit(0)
#SeqNumber-number of the seq send
#Sock-socket
#IP-IP add
#time_begin-for finding the Timeout
#window_size-getting the corect window size
def SendInitialPacket(SeqNumber, Sock, IP, Port, PacketNumber,time_begin,window_size):#sends Inital syncronyzation packet
    flag="s"#Flag for syncronyzation
    msg="HI"#first msg sent
    pickled_data=pickle.dumps([SeqNumber,flag,msg])#pickling the packet
    DestAddress=(IP, Port)#Dest IP and Port
    Sock.sendto(pickled_data, DestAddress)#sending
    try:
        Sock.settimeout(Timeout)#Timeout for syncronyzation ack
        while True:
            if signal.signal(signal.SIGINT, signal_handler)==1:#for ctrl+c
                break
            data, address= Sock.recvfrom(Port)#recv the first ack
            text=pickle.loads(data)#unpickling the data
            if text:
                AckFor=text[0]#first is ack for what seq num
                if (AckFor == 0):#first ack neads to be 0
                    PacketNumber=0
                    time_stop=time.time()#for getting the window_size
                    time_for_window=time_stop-time_begin#stop - start time(RTT)
                if time_for_window>1:#if RTT>1 it is the last case
                    window_size=2905#use this window size
                elif time_for_window<=1:#is RTT<=1 it is not the 5 case
                    window_size=250#use this window size
                return PacketNumber,window_size
    except:
        signal.signal(signal.SIGINT, signal_handler)#for ctrl+c
        return PacketNumber,window_size
#IP-where to send Data
#Port-what port is in use
#Packsize-how much data to get for sending
#PacketNumber-which PN we are Sending
#Data_PW-dict for PacketNumber and data
#start=0when we have no more data to read we stop
def SendPacket(IP, Port, Sock, Packsize, PacketNumber, Data_PW, start,Timeout,window_size):#Sending data
    ack_w={}#dictionary of packets we have sand with data
    for SN in range(window_size):
        if len(Data_PW)!=0:#if there was a lost in last window
            flag="d"#flag for data
            PN=list(Data_PW.keys())[0]#Lost PacketNumber
            PN_DATA=list(Data_PW.values())[0]#Lost Data
            PacketData=pickle.dumps([PN,flag,PN_DATA])#Pickling the packet
            server_address=(IP,Port)
            ack_w[PN]=PN_DATA#pitting them in a dict for waiting
            del Data_PW[PN]#del the one we send
            Sock.sendto(PacketData,server_address)#sending
        elif start==1:#when nothing is lost or we empty the dictionary Data_PW
            senddata = sys.stdin.buffer.read(Packsize)#getting new data
            ack_w[PacketNumber]=senddata#pitting them in a dict for waiting
            flag="d"#flag for data
            PacketData=pickle.dumps([PacketNumber,flag,senddata])#pickling it
            server_address=(IP,Port)
            Sock.sendto(PacketData,server_address)#sending
            if not (senddata):#when we have no more data to read we stop
                start=0
            PacketNumber+=1
        if signal.signal(signal.SIGINT, signal_handler)==1:
            break
    if window_size==2905:#if it is the 5 case we need sleep
        time.sleep(0.13)
    PacketNumber,Data_PW, Timeout,window_size=wait_ack(Timeout,window_size,PacketNumber,Packsize,ack_w)
    return PacketNumber, Data_PW, start, Timeout,window_size
#Timeout-how much we wait for ack to come
#ack_w-dictionary of packets we have sand with data
def wait_ack(Timeout,window_size,PacketNumber,Packsize,ack_w):#waits for ack
    ack_r=[]#list for positive ack
    ack_no=[]#list for negativ ack
    Data_PW={}#dict for PacketNumber and data
    try:
        while (len(ack_r)+len(ack_no))!=window_size:#till we get ack for all we send
            Sock.settimeout(Timeout)#timeout
            time_start = time.time()#for the next timeout
            data,address=Sock.recvfrom(Port)#recv ack
            text=pickle.loads(data)
            if text:
                AckFor=text[0]
                Ack=text[1]
                if Ack=="ACK":#positive ack received
                    ack_r.append(AckFor)#list for pos ack
                    time_now = time.time()#getting the now timeout
                    if AckFor in ack_w:#del the ones we get from the dict
                        del ack_w[AckFor]
                elif Ack=="NACK":#negative ack received
                    time_now = time.time()#getting the now timeout
                    ack_no.append(AckFor)#list for negative ack
            Timeout=(time_now-time_start)*1.05#time countet and +5%
            if signal.signal(signal.SIGINT, signal_handler)==1:#ctrl+c
                break
        if len(ack_w)!=0:#making a copy of what to send in next window
            Data_PW=ack_w.copy()#for sending again
        else:
            Data_PW={}
        ack_w.clear()
        del ack_r[:]
        return PacketNumber,Data_PW,Timeout,window_size

    except:#in case of timeout(missing ack)
        signal.signal(signal.SIGINT, signal_handler)
        for i in ack_r:#if something is left
            if i in ack_w:
                del ack_w[i]
        if len(ack_w)!=0:
            Data_PW=ack_w.copy()
        else:
            Data_PW={}
        ack_w.clear()
        del ack_r[:]
        return PacketNumber,Data_PW,Timeout,window_size
#Last_SN-last seq num
#Final-flag
#time_for_timeout-timeout
def SendFinalPacket (Sock, IP, Port,Last_SN, Final,time_for_timeout):#Sends Final Packet
    flag="f"#flag sent
    mess="SAYONARA"#msg sent
    PacketData=pickle.dumps([Last_SN,flag,mess])#pickling it
    server_address = (IP, Port)
    Sock.sendto(PacketData, server_address)#sending
    Timeout=time_for_timeout
    Sock.settimeout(Timeout)
    while True:
        if signal.signal(signal.SIGINT, signal_handler)==1:
            break
        data, address= Sock.recvfrom(Port)#receive final ack
        text=pickle.loads(data)
        if text:
            Ack_Fin=text[0]
            if (window_size == Ack_Fin):
                Final=1
            return Final

IP, Port = GetArguments()#Getting inline arguments

Sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)#creating udp socket
PacketNumber=-1
SeqNumber=0
time_begin=time.time()
while(PacketNumber!=0):#we get 0 when they are synchronized
    PacketNumber,window_size=SendInitialPacket(SeqNumber, Sock, IP, Port, PacketNumber,time_begin,window_size)#sending first pocket
    signal.signal(signal.SIGINT, signal_handler)#ctrl+c

PacketNumber=0#we start from 0
Data_PW=[]
senddata=0
start=1#while it is 1 we send data
time_for_timeout=Timeout
while(start==1) or (len(Data_PW)!=0):#till we send everything and start==1
    PacketNumber, Data_PW, start, Timeout,window_size= SendPacket(IP, Port, Sock, Packsize, PacketNumber, Data_PW, start, Timeout,window_size)#sending data
    signal.signal(signal.SIGINT, signal_handler)#ctrl+c

Last_SN=window_size#last seq num
Final=0#we send final pocket till flag is 1

time_for_timeout=1.1
while(Final == 0):#Sending final packet
    Final=SendFinalPacket(Sock, IP, Port,Last_SN, Final,time_for_timeout)#sending final pocket
    signal.signal(signal.SIGINT, signal_handler)#ctrl+c
sys.exit()
