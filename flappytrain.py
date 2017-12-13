from itertools import cycle
import random
import sys
import json

import pygame
from pygame.locals import *
#############################################################  BOT
'''
Training model: Q-Learning
    
    <s_0 a_0 r_1, s_1 a_1 r_2,...> History array : for the action a_i taken in state s_i, the reward is r_(i+1).
    [S A R S'] Experience entry Where S is state, A is action, R is reward, S' is the next state which is the result of the action.

    Agent	: Bird
    
    States:
        x 	: Horizontal distance from the pipes to the bird
        y 	: Vertaical distance from the lower pipe to the bird (We don't consider upper pipes. 
		  The distance between 2 pipes are constant and the vertial distance from the 
		  bird to the upper pipe will be (100 - y))
        vel 	: y - velocity of the bird. (We don't use x - velocity as it is constant)

    State-Space : Since there are about 800,000 states, we will consider 
		  grids of 10 x 10 and then approximate to the nearest grid.
		  This will bring down the number of states to 8,000.
        x	: [-40,  490]
        y	: [-300, 420]
        vel	: [-10,  11]

    Actions:
        Nothing : Does not jump in the particular square. 
        Jump 	: Jumps in that square

    Rewards:
        If the bird is dead because of a decision, we award it -1000 points.
        For all other actions, we award 1 point, since it is unclear if it is helping or hurting.
'''
    
alpha = 0.8			# learning rate alpha
prev_xyv = "420_240_0"		# Previous state. Initializing with the first state (maximum x and y distances)
prev_action = 0			# first action defaulting to not jumping
moves = []			# tracks the previous movements
topscore = 0
qvalues = {}
prevPipe = None
qvalues[prev_xyv] = [0, 0]

# Get q-values from a file if the file is present, otherwise, initalize a set of qvalues
'''
def initialize_empty_qvals():
    print "Initializing empty set of q-Values"
    for x in list(range(-40, 141, 10)) + list(range(140, 491, 70)):
        for y in list(range(-300,180,10)) + list(range(180, 421, 60)):
            for vel in range(-9,11,1):
                qvalues[str(x)+'_'+str(y)+'_'+str(vel)] = [0,0]
    fd = open('qvalues.json', 'w')
    json.dump(qvalues, fd)
    fd.close()
'''
try:
    fil = open('qvalues.json', 'r')
    qvalues = json.load(fil)
    fil.close()
except IOError:
    print "initialising new set of qvals"

def get_state_key(x, y, vel):
    global qvalues
    statekey =  str(round_off(x)) + '_' + str(round_off(y)) + '_' + str(vel)
    if statekey in qvalues.keys():
	return statekey
    qvalues[statekey] = [0,0]
    return statekey

def round_off(x):
    retx = x
    if x % 10 > 5:
        retx = x - (x % 10) + 10
    else:
        retx = x - (x % 10)
    return int(retx)

def decide(x, y, vel):
    global qvalues, alpha, prev_xyv, prev_action, moves 
    curr_xyv = get_state_key(x, y, vel)
    
    moves.append( [prev_xyv, prev_action, curr_xyv] ) 
    prev_xyv = curr_xyv					

    if qvalues[curr_xyv][0] >= qvalues[curr_xyv][1]:
        prev_action = 0
    else:
        prev_action = 1
    
    return prev_action

def update(cause):
    global qvalues, alpha, prev_xyv, prev_action, moves
    history = list(reversed(moves))
    
    #Some flags for death causes
    top_pipe_collision = True if cause == 'U' else False
    bottom_pipe_collision = True if cause == 'L' else False
    fall_on_ground = True if cause == 'G' else False
    print cause

    '''
     If bird falls on ground, we are penalizing each decision that caused the player to fall.
     If bird hits the top pipe, we penalize the last decision to jump that caused the bird to hit the pipe
     If bird hits the lower pipe, we penalize the last few decisions to not jump
    '''
    if top_pipe_collision:
        i = 1
        flag = True
        for exp in history:
            state = exp[0]
            act = exp[1]
            next_state = exp[2]
            if i <= 2:
                qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (-1000 + max(qvalues[next_state])))
            else:
                if act and flag: # penalise the first jump
                    qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (-1000 + max(qvalues[next_state])))
                    flag = False
                else:
                    qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (1 + max(qvalues[next_state])))
            i += 1
    
    elif bottom_pipe_collision:
        i = 1
        flag = True
        for exp in history:
            state = exp[0]
            act = exp[1]
            next_state = exp[2]
            if i <= 2 and not act:
                qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (-1000 + max(qvalues[next_state])))
            else:
                flag = False
                qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (1 + max(qvalues[next_state])))
            i += 1
    
    elif fall_on_ground:
        i = 1
        flag = True
        for exp in history:
            state = exp[0]
            act = exp[1]
            next_state = exp[2]
            if flag and not act:
                qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (-1000 + max(qvalues[next_state])))
            else:
                flag = False
                qvalues[state][act] = ((1 - alpha) * qvalues[state][act]) + (alpha * (1 + max(qvalues[next_state])))
            i += 1

    moves = [] 			# start over

#Update values in the file so that next time, it plays with experience
def dump_json():
    global qvalues, alpha, prev_xyv, prev_action, moves
    fil = open('qvalues.json', 'w')
    json.dump(qvalues, fil)
    fil.close()
    print('Q-values updated')

#############################################################  GAME
FPS = 90
SCREENWIDTH  = 288
SCREENHEIGHT = 512
# amount by which base can maximum shift to left
PIPEGAPSIZE  = 100 # gap between upper and lower part of pipe
BASEY        = SCREENHEIGHT * 0.79
# image, sound and hitmask  dicts
IMAGES, SOUNDS, HITMASKS = {}, {}, {}

# list of all possible players (tuple of 3 positions of flap)
PLAYERS_LIST = (
    # red bird
    (
        'assets/sprites/redbird-upflap.png',
        'assets/sprites/redbird-midflap.png',
        'assets/sprites/redbird-downflap.png',
    ),
    # blue bird
    (
        # amount by which base can maximum shift to left
        'assets/sprites/bluebird-upflap.png',
        'assets/sprites/bluebird-midflap.png',
        'assets/sprites/bluebird-downflap.png',
    ),
    # yellow bird
    (
        'assets/sprites/yellowbird-upflap.png',
        'assets/sprites/yellowbird-midflap.png',
        'assets/sprites/yellowbird-downflap.png',
    ),
)

# list of backgrounds
BACKGROUNDS_LIST = (
    'assets/sprites/background-day.png',
    'assets/sprites/background-night.png',
)

# list of pipes
PIPES_LIST = (
    'assets/sprites/pipe-green.png',
    'assets/sprites/pipe-red.png',
)


try:
    xrange
except NameError:
    xrange = range


def main():
    global SCREEN, FPSCLOCK, qvalues, alpha, prev_xyv, prev_action, moves 
    pygame.init()
    FPSCLOCK = pygame.time.Clock()
    SCREEN = pygame.display.set_mode((SCREENWIDTH, SCREENHEIGHT))
    pygame.display.set_caption('Flappy Bird')

    # numbers sprites for score display
    IMAGES['numbers'] = (
        pygame.image.load('assets/sprites/0.png').convert_alpha(),
        pygame.image.load('assets/sprites/1.png').convert_alpha(),
        pygame.image.load('assets/sprites/2.png').convert_alpha(),
        pygame.image.load('assets/sprites/3.png').convert_alpha(),
        pygame.image.load('assets/sprites/4.png').convert_alpha(),
        pygame.image.load('assets/sprites/5.png').convert_alpha(),
        pygame.image.load('assets/sprites/6.png').convert_alpha(),
        pygame.image.load('assets/sprites/7.png').convert_alpha(),
        pygame.image.load('assets/sprites/8.png').convert_alpha(),
        pygame.image.load('assets/sprites/9.png').convert_alpha()
    )

    # game over sprite
    IMAGES['gameover'] = pygame.image.load('assets/sprites/gameover.png').convert_alpha()
    # message sprite for welcome screen
    IMAGES['message'] = pygame.image.load('assets/sprites/message.png').convert_alpha()
    # base (ground) sprite
    IMAGES['base'] = pygame.image.load('assets/sprites/base.png').convert_alpha()

    # sounds
    if 'win' in sys.platform:
        soundExt = '.wav'
    else:
        soundExt = '.ogg'

    SOUNDS['die']    = pygame.mixer.Sound('assets/audio/die' + soundExt)
    SOUNDS['hit']    = pygame.mixer.Sound('assets/audio/hit' + soundExt)
    SOUNDS['point']  = pygame.mixer.Sound('assets/audio/point' + soundExt)
    SOUNDS['swoosh'] = pygame.mixer.Sound('assets/audio/swoosh' + soundExt)
    SOUNDS['wing']   = pygame.mixer.Sound('assets/audio/wing' + soundExt)

    while True:
        # select random background sprites
        randBg = random.randint(0, len(BACKGROUNDS_LIST) - 1)
        IMAGES['background'] = pygame.image.load(BACKGROUNDS_LIST[randBg]).convert()

        # select random player sprites
        randPlayer = random.randint(0, len(PLAYERS_LIST) - 1)
        IMAGES['player'] = (
            pygame.image.load(PLAYERS_LIST[randPlayer][0]).convert_alpha(),
            pygame.image.load(PLAYERS_LIST[randPlayer][1]).convert_alpha(),
            pygame.image.load(PLAYERS_LIST[randPlayer][2]).convert_alpha(),
        )

        # select random pipe sprites
        pipeindex = random.randint(0, len(PIPES_LIST) - 1)
        IMAGES['pipe'] = (
            pygame.transform.rotate(
                pygame.image.load(PIPES_LIST[pipeindex]).convert_alpha(), 180),
            pygame.image.load(PIPES_LIST[pipeindex]).convert_alpha(),
        )

        # hismask for pipes
        HITMASKS['pipe'] = (
            getHitmask(IMAGES['pipe'][0]),
            getHitmask(IMAGES['pipe'][1]),
        )

        # hitmask for player
        HITMASKS['player'] = (
            getHitmask(IMAGES['player'][0]),
            getHitmask(IMAGES['player'][1]),
            getHitmask(IMAGES['player'][2]),
        )

        movementInfo = showWelcomeAnimation()
        crashInfo = mainGame(movementInfo)
        #showGameOverScreen(crashInfo)


def showWelcomeAnimation():
    """Shows welcome screen animation of flappy bird"""
    # index of player to blit on screen
    playerIndex = 0
    playerIndexGen = cycle([0, 1, 2, 1])
    # iterator used to change playerIndex after every 5th iteration
    loopIter = 0

    playerx = int(SCREENWIDTH * 0.2)
    playery = int((SCREENHEIGHT - IMAGES['player'][0].get_height()) / 2)

    messagex = int((SCREENWIDTH - IMAGES['message'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)

    basex = 0
    # amount by which base can maximum shift to left
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # player shm for up-down motion on welcome screen
    playerShmVals = {'val': 0, 'dir': 1}

    SOUNDS['wing'].play()
    return {
        'playery': playery + playerShmVals['val'],
        'basex': basex,
        'playerIndexGen': playerIndexGen,
    }


def mainGame(movementInfo):
    global topscore, prevPipe, moves
    score = playerIndex = loopIter = 0
    playerIndexGen = movementInfo['playerIndexGen']
    playerx, playery = int(SCREENWIDTH * 0.2), movementInfo['playery']

    basex = movementInfo['basex']
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # get 2 new pipes to add to upperPipes lowerPipes list
    newPipe1 = getRandomPipe()
    newPipe2 = getRandomPipe()

    # list of upper pipes
    upperPipes = [
        {'x': SCREENWIDTH + 200, 'y': newPipe1[0]['y']},
        {'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': newPipe2[0]['y']},
    ]

    # list of lowerpipe
    lowerPipes = [
        {'x': SCREENWIDTH + 200, 'y': newPipe1[1]['y']},
        {'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': newPipe2[1]['y']},
    ]

    pipeVelX = -4

    # player velocity, max velocity, downward accleration, accleration on flap
    playerVelY    =  -9   # player's velocity along Y, default same as playerFlapped
    playerMaxVelY =  10   # max vel along Y, max descend speed
    playerMinVelY =  -8   # min vel along Y, max ascend speed
    playerAccY    =   1   # players downward accleration
    playerRot     =  45   # player's rotation
    playerVelRot  =   3   # angular speed
    playerRotThr  =  20   # rotation threshold
    playerFlapAcc =  -9   # players speed on flapping
    playerFlapped = False # True when player flaps

    while True:
        if -playerx + lowerPipes[0]['x'] > -30: myPipe = lowerPipes[0]
        else: myPipe = lowerPipes[1]
        '''
        if prevPipe != myPipe and prevPipe != None:
            flag = False
            for exp in reversed(moves):
                if flag:
                    print exp
                if exp[1]:
                    print exp
                    flag = True
                    
            #moves = []
            prevPipe = myPipe
        '''

        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                print "quitting"
                dump_json()
                pygame.quit()
                sys.exit()
            if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP): # add another check here to see if bot is playing
                if playery > -2 * IMAGES['player'][0].get_height():
                    playerVelY = playerFlapAcc
                    playerFlapped = True
                    SOUNDS['wing'].play()
                
        if(decide(-playerx + myPipe['x'], - playery + myPipe['y'], playerVelY )):
            if playery > -2 * IMAGES['player'][0].get_height():
                playerVelY = playerFlapAcc
                playerFlapped = True
                SOUNDS['wing'].play()


        # check for crash here
        crashTest = checkCrash({'x': playerx, 'y': playery, 'index': playerIndex},
                               upperPipes, lowerPipes)
        if crashTest[0]:
            # here is where we should update the qvalues array.
            # comment the line if you want to stop learning
            update(crashTest[2])
            if(score > topscore):
                topscore = score
            print str(score)+'-'+str(topscore)
            return {
                'y': playery,
                'groundCrash': crashTest[1],
                'basex': basex,
                'upperPipes': upperPipes,
                'lowerPipes': lowerPipes,
                'score': score,
                'playerVelY': playerVelY,
                'playerRot': playerRot
            }

        # check for score
        playerMidPos = playerx + IMAGES['player'][0].get_width() / 2
        for pipe in upperPipes:
            pipeMidPos = pipe['x'] + IMAGES['pipe'][0].get_width() / 2
            if pipeMidPos <= playerMidPos < pipeMidPos + 4:
                score += 1
                SOUNDS['point'].play()

        # playerIndex basex change
        if (loopIter + 1) % 3 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 100) % baseShift)

        # rotate the player
        if playerRot > -90:
            playerRot -= playerVelRot

        # player's movement
        if playerVelY < playerMaxVelY and not playerFlapped:
            playerVelY += playerAccY
        if playerFlapped:
            playerFlapped = False

            # more rotation to cover the threshold (calculated in visible rotation)
            playerRot = 45

        playerHeight = IMAGES['player'][playerIndex].get_height()
        playery += min(playerVelY, BASEY - playery - playerHeight)

        # move pipes to left
        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            uPipe['x'] += pipeVelX
            lPipe['x'] += pipeVelX

        # add new pipe when first pipe is about to touch left of screen
        if 0 < upperPipes[0]['x'] < 5:
            newPipe = getRandomPipe()
            upperPipes.append(newPipe[0])
            lowerPipes.append(newPipe[1])

        # remove first pipe if its out of the screen
        if upperPipes[0]['x'] < -IMAGES['pipe'][0].get_width():
            upperPipes.pop(0)
            lowerPipes.pop(0)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            SCREEN.blit(IMAGES['pipe'][0], (uPipe['x'], uPipe['y']))
            SCREEN.blit(IMAGES['pipe'][1], (lPipe['x'], lPipe['y']))

        SCREEN.blit(IMAGES['base'], (basex, BASEY))
        # print score so player overlaps the score
        showScore(score)

        # Player rotation has a threshold
        visibleRot = playerRotThr
        if playerRot <= playerRotThr:
            visibleRot = playerRot
        
        playerSurface = pygame.transform.rotate(IMAGES['player'][playerIndex], visibleRot)
        SCREEN.blit(playerSurface, (playerx, playery))

        pygame.display.update()
        FPSCLOCK.tick(FPS)

def playerShm(playerShm):
    """oscillates the value of playerShm['val'] between 8 and -8"""
    if abs(playerShm['val']) == 8:
        playerShm['dir'] *= -1

    if playerShm['dir'] == 1:
         playerShm['val'] += 1
    else:
        playerShm['val'] -= 1


def getRandomPipe():
    """returns a randomly generated pipe"""
    # y of gap between upper and lower pipe
    gapY = random.randrange(0, int(BASEY * 0.6 - PIPEGAPSIZE))
    gapY += int(BASEY * 0.2)
    pipeHeight = IMAGES['pipe'][0].get_height()
    pipeX = SCREENWIDTH + 10

    return [
        {'x': pipeX, 'y': gapY - pipeHeight},  # upper pipe
        {'x': pipeX, 'y': gapY + PIPEGAPSIZE}, # lower pipe
    ]


def showScore(score):
    """displays score in center of screen"""
    scoreDigits = [int(x) for x in list(str(score))]
    totalWidth = 0 # total width of all numbers to be printed

    for digit in scoreDigits:
        totalWidth += IMAGES['numbers'][digit].get_width()

    Xoffset = (SCREENWIDTH - totalWidth) / 2

    for digit in scoreDigits:
        SCREEN.blit(IMAGES['numbers'][digit], (Xoffset, SCREENHEIGHT * 0.1))
        Xoffset += IMAGES['numbers'][digit].get_width()


def checkCrash(player, upperPipes, lowerPipes):
    """returns True if player collders with base or pipes."""
    pi = player['index']
    player['w'] = IMAGES['player'][0].get_width()
    player['h'] = IMAGES['player'][0].get_height()

    # if player crashes into ground
    if player['y'] + player['h'] >= BASEY - 1:
        return [True, True, "G"]
    else:

        playerRect = pygame.Rect(player['x'], player['y'],
                      player['w'], player['h'])
        pipeW = IMAGES['pipe'][0].get_width()
        pipeH = IMAGES['pipe'][0].get_height()

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            # upper and lower pipe rects
            uPipeRect = pygame.Rect(uPipe['x'], uPipe['y'], pipeW, pipeH)
            lPipeRect = pygame.Rect(lPipe['x'], lPipe['y'], pipeW, pipeH)

            # player and upper/lower pipe hitmasks
            pHitMask = HITMASKS['player'][pi]
            uHitmask = HITMASKS['pipe'][0]
            lHitmask = HITMASKS['pipe'][1]

            # if bird collided with upipe or lpipe
            uCollide = pixelCollision(playerRect, uPipeRect, pHitMask, uHitmask)
            lCollide = pixelCollision(playerRect, lPipeRect, pHitMask, lHitmask)

            if uCollide:
                return [True, False, "U"]
            elif lCollide:
                return [True, False, "L"]

    return [False, False]

def pixelCollision(rect1, rect2, hitmask1, hitmask2):
    """Checks if two objects collide and not just their rects"""
    rect = rect1.clip(rect2)

    if rect.width == 0 or rect.height == 0:
        return False

    x1, y1 = rect.x - rect1.x, rect.y - rect1.y
    x2, y2 = rect.x - rect2.x, rect.y - rect2.y

    for x in xrange(rect.width):
        for y in xrange(rect.height):
            if hitmask1[x1+x][y1+y] and hitmask2[x2+x][y2+y]:
                return True
    return False

def getHitmask(image):
    """returns a hitmask using an image's alpha."""
    mask = []
    for x in xrange(image.get_width()):
        mask.append([])
        for y in xrange(image.get_height()):
            mask[x].append(bool(image.get_at((x,y))[3]))
    return mask

if __name__ == '__main__':
    main()
