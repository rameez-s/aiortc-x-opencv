# SERVER
import cv2
import numpy as np
import argparse
import asyncio
from av import VideoFrame
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.signaling import BYE, TcpSocketSignaling, add_signaling_arguments, create_signaling

class BallBounce():
    def __init__(self):
        '''
        Initializes image animation variables

        '''
        self.WIDTH = 720
        self.HEIGHT = 480
        self.dx = 10
        self.dy = 10
        self.xCo = 360
        self.yCo = 240
        self.ballRad = 15
        self.ballColor = (0, 0, 255)
        self.i = 0
        self.predX = 0
        self.predY = 0

    def collision(self, maxBound, x):
        '''
        Checks for points out of bounds.
                Parameters:
                        maxBound (int): max value
                        x (int): value

                Return:
                        True if out of bounds.
                        False otherwise.

        '''
        if (x >= maxBound or x <= 0):
            return True
        return False

    def ballBounce(self):
        '''
        Updates x, y coordinates and returns new image frame.
                Return:
                        img (numpy array): image frame
                        x (int): true x coordinate for image
                        y (int): true y coordinate for image

        '''
        img = np.zeros((self.HEIGHT, self.WIDTH, 3), dtype = 'uint8')
        if self.collision(self.WIDTH, self.xCo):
            self.dx *= -1
        if self.collision(self.HEIGHT, self.yCo):
            self.dy *= -1

        self.xCo += self.dx
        self.yCo += self.dy
        self.i += 1
        cv2.circle(img, (self.xCo, self.yCo), self.ballRad, self.ballColor, -1)
        return (img, self.xCo, self.yCo)

class FrameConstruct(VideoStreamTrack):
    '''
    Extension of VideoStreamTrack class. This class uses the BallBounce class
    to generate each frame then package it for transfer to client.

    '''

    kind = "video"

    def __init__(self, ball):
        '''
        Initializes ball variables.

                Parameters:
                        ball (BallBounce): object

        '''
        super().__init__()
        self.ball =  ball
        self.x = 0
        self.y = 0


    async def recv(self):
        '''
        Package image into frame.

        '''
        pts, time_base = await self.next_timestamp()
        img, self.x, self.y = self.ball.ballBounce()
        frame = VideoFrame.from_ndarray(img, format = "bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame


async def consume_signaling(pc, signaling):
    '''
    Maintains signal receive port and ICE candidate handshake
    Source:
    https://github.com/aiortc/aiortc/blob/f85f7133435b54ce9de5f2f391c0c0ef0014e820/examples/datachannel-cli/cli.py

            Parameters:
                    pc (RTCPeerConnection): Remote peer object
                    signaling (TcpSocketSignaling): Remote signal object

    '''
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")
            break


def compareCoords(x1, y1, x2, y2):
    '''
    Prints final correct and predicted coordinates, and their error as by
    distance formula between two points.

            Parameters:
                    x1 (int): coordinate value
                    y1 (int): coordinate value
                    x2 (int): coordinate value
                    y2 (int): coordinate value


    '''
    error = ((x1 - x2)**2 + (y1 - y2)**2)**(1/2)

    print("Real Center: " + str(x1) + ", " + str(y1))
    print("Pred Center: " + str(x2) + ", " + str(y2))
    print("Error: " + str(error))


async def main(pc, signaling):
    '''
    Initializes RTC Event Listeners and client offer-answer handshake.

            Parameters:
                    pc (RTCPeerConnection): Remote peer object
                    signaling (TcpSocketSignaling): Remote signal object

    '''
    ball = BallBounce()
    track = FrameConstruct(ball)
    params = await signaling.connect()

    dc = pc.createDataChannel('chat')

    @pc.on('icegatheringstatechange')
    def pcIceGatherStateChange():
        print('NEW Ice Gathering State %s' % pc.iceGatheringState)

    @pc.on('iceconnectionstatechange')
    def pcIceConnectionStateChange():
        print('NEW Ice Connection State %s' % pc.iceConnectionState)

    @pc.on('signalingstatechange')
    def pcSignalingStateChange():
        print('NEW Signaling State %s' % pc.signalingState)

    @pc.on('track')
    def pcTrack():
        print('NEW track %s' % track.id)

    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        async def on_message(message):
            '''
            Receives client's predicted coordinates and compares

                Parameters:
                    message (str): encoded (x,y) tuple 'coords:x,y'

            '''
            if (message.startswith("coords")):
                coords = message[7:].split(",")
                compareCoords(ball.xCo, ball.yCo, int(coords[0]), int(coords[1]))

    pc.addTrack(track)
    await pc.setLocalDescription(await pc.createOffer())
    await signaling.send(pc.localDescription)

    await consume_signaling(pc, signaling)


if __name__ == "__main__":
    print("Server started")
    parser = argparse.ArgumentParser(description="Ball Position Detector - Server")
    add_signaling_arguments(parser)

    args = parser.parse_args()

    signaling = TcpSocketSignaling(args.signaling_host, args.signaling_port)
    pc = RTCPeerConnection()


    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            main(pc, signaling)
        )
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())
