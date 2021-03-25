import socket, sys, os, random, pickle, signal

def CheckArg():#Getting arguments
    if (len(sys.argv)!=3):#needs 3 arguments
        sys.exit()
    IP=sys.argv[1]#IP is second
    Port=sys.argv[2]#port is third
    try:
        Port=int(Port)
    except:
        sys.exit()
    if (Port<1025) or (Port>65535):#Port should be between this two numbers not to interfere
        sys.exit()
    return IP, Port

def signal_handler(sig, frame):#Ctrl+c
    sys.exit(0)

def ParseData(text):#separating parts of message
    SeqNumber=text[0]
    Flag=text[1]
    Data=text[2]
    return SeqNumber, Flag, Data

def SendAck(PacketNumber, Sock, Address):#sending Ack
    signal.signal(signal.SIGINT, signal_handler)#ctrl+c
    flag="ACK"#flag for positive ack
    AckData=pickle.dumps([PacketNumber,flag])#pickling the ack
    Sock.sendto(AckData, Address)#sending

def SendAck_negative(PacketNumber, Sock, Address):#sending negative Ack
    signal.signal(signal.SIGINT, signal_handler)#ctrl+c
    flag="NACK"#negative ack
    AckData=pickle.dumps([PacketNumber,flag])#pickling it up
    Sock.sendto(AckData, Address)#sending

IP, Port=CheckArg()#calling function to get arguments
Sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)#creating udp socket
Sock.bind((IP,Port))
SeqNumber=0
PacketNumber=0
Packet_Wait={}#dict for data that is waiting
Lost=[]#list of pocket num that are missing

while True:
    if signal.signal(signal.SIGINT, signal_handler)==1:#ctrl+c
        break
    Data, Address= Sock.recvfrom(Port)#getting the pocket
    if Data:
        unpickled_data=pickle.loads(Data)#unpickling it
        SeqNum, Flag, Data = ParseData(unpickled_data)
        if Flag == "s":#check if the packet is synchronizing packet
            if SeqNum==0:#checking if we get the corect pocketNumber we expect
                SendAck(SeqNum, Sock, Address)#senging ack
                if PacketNumber == 0:#we will start from 0Pocket number in sending of data
                    PacketNumber=0
        elif (Flag =="d"):#if flag is data
            if (PacketNumber==SeqNum) and (len(Packet_Wait)==0):#if we get the PacketNumber we expect and the dict is empty
                SendAck(PacketNumber,Sock,Address)#sending ack
                sys.stdout.buffer.write(Data)#putting it in the new file
                PacketNumber+=1

            elif (PacketNumber==SeqNum) and (len(Packet_Wait)!=0):#if the dict is not empty we put it in the dict till we get the one we missed
                SendAck(PacketNumber, Sock, Address)#send ack
                Packet_Wait[PacketNumber]=Data#putting it in the dict
                Packet_Wait=dict(sorted(Packet_Wait.items()))#sorting the dict
                PacketNumber+=1

            elif (PacketNumber<SeqNum):#there is a lost of packet, we get bigger PacketNumber then we expect
                SendAck(SeqNum, Sock, Address)#sending ack
                while PacketNumber!=SeqNum:#increase till they are equal
                    SendAck_negative(PacketNumber, Sock, Address)#sending negativ ack
                    Lost.append(PacketNumber)#adding in the list what is missing
                    PacketNumber+=1
                Packet_Wait[PacketNumber]=Data#adding in the dict what data and PN arrived
                Packet_Wait=dict(sorted(Packet_Wait.items()))#sorting the dict
                Lost.sort()#sorting the list
                PacketNumber+=1

            elif (PacketNumber>SeqNum):#if we get something we missed
                Momentum=PacketNumber#saving the PN
                if SeqNum in Lost:#if it is in the missing list(so it is not a duplicate)
                    if SeqNum==Lost[0]:#if it is the first in the list
                        SendAck(SeqNum,Sock,Address)#sending ack
                        sys.stdout.buffer.write(Data)#putting it in the now file
                        del Lost[0]#del the first element we have now
                        if len(Packet_Wait)!=0:#if the list is not empty
                            Waiting=SeqNum+1
                            while Waiting==list(Packet_Wait.keys())[0]:#to fint if the next one we need to save in the file is in the dict first
                                PacketNumber=list(Packet_Wait.keys())[0]#getting the first one from the dict(the key)
                                Data=list(Packet_Wait.values())[0]#getting the data from the dict(the value)
                                sys.stdout.buffer.write(Data)#putting it in the file
                                del Packet_Wait[PacketNumber]#del the first one in the dict
                                if len(Packet_Wait)==0:#if the dict is empty we break
                                    break
                                Waiting+=1
                    else:#if it is not the first in the list we add it in the dist
                        SendAck(SeqNum,Sock,Address)#sending positive ack
                        Packet_Wait[SeqNum]=Data#putting in the dict
                        Packet_Wait=dict(sorted(Packet_Wait.items()))#sort the dict
                        Lost.remove(SeqNum)#remove the one we have now
                        Lost.sort()#sort the list
                else:
                    SendAck(SeqNum,Sock,Address)#if we get a duplicate we just send a ack
                PacketNumber=Momentum#we saved the PN in Momentum
            else:
                SendAck(SeqNum,Sock,Address)
        elif Flag == "f":#if the packet is final packet(flag=f)
            for i in range(5):#increasing the chance for the final ack
                SendAck(SeqNum, Sock, Address)#sending ack
            sys.exit()
