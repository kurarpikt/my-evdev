import evdev
import time

from evdev import ecodes

UP = 0
DOWN = 1
NORMAL = 'normal'
MOD = 'mod'
INJECT = 'inject'
MAPPED = 'mapped'
KEY_MAP = {
  ecodes.KEY_LEFTALT: {
    ecodes.KEY_D: [ecodes.KEY_LEFTCTRL, ecodes.KEY_TAB],
    ecodes.KEY_S: [ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_TAB]
  },
  ecodes.KEY_J: {
    ecodes.KEY_E: [ecodes.KEY_UP],
    ecodes.KEY_D: [ecodes.KEY_DOWN],
    ecodes.KEY_S: [ecodes.KEY_LEFT],
    ecodes.KEY_F: [ecodes.KEY_RIGHT],
    ecodes.KEY_W: [ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFT],
    ecodes.KEY_R: [ecodes.KEY_LEFTCTRL,ecodes.KEY_RIGHT],
    ecodes.KEY_A: [ecodes.KEY_HOME],
    ecodes.KEY_G: [ecodes.KEY_END]
  },
  ecodes.KEY_RIGHTSHIFT: {
    ecodes.KEY_E: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_UP],
    ecodes.KEY_D: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_DOWN],
    ecodes.KEY_S: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFT],
    ecodes.KEY_F: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHT],
    ecodes.KEY_W: [ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFT],
    ecodes.KEY_R: [ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHT],
    ecodes.KEY_A: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_HOME],
    ecodes.KEY_G: [ecodes.KEY_LEFTSHIFT, ecodes.KEY_END]
  }
}

currentState = NORMAL
logState = []
currentMod = ''

class keystroke:
    def __init__(self):
        self.state = 0
        self.keycode = None
        self.keystate = None

    def input(self, ev):
        if self.state == 0 and isinstance(ev, evdev.InputEvent):
            if ev.code != ecodes.MSC_SCAN and ev.type != ecodes.EV_MSC:
                print("Special keypress: %s %s" % (ecodes.EV[ev.type], ecodes.MSC[ev.code]))
            self.state += 1
            return

        if self.state == 1 and isinstance(ev, evdev.KeyEvent):
            self.keycode = ecodes.ecodes[ev.keycode]
            self.keystate = ev.keystate
            self.state += 1
            return

        if self.state == 2 and isinstance(ev, evdev.SynEvent):
            self.state += 1
            return

        self.reset()

    def finished(self):
        return self.state == 3

    def reset(self):
        self.state = 0

def __inject(keycode, keystate):
    global ui

    t = time.time()
    sec = int(t)
    usec = int((t - int(t)) * 1000000)

    ui.write(ecodes.EV_MSC, ecodes.MSC_SCAN, keycode)
    ui.write(ecodes.EV_KEY, keycode, keystate)
    ui.syn()

class State():
    def __init__(self, judge, nextState, action = []):
        self.judge = judge
        self.nextState = nextState
        self.action = action

def inject_mod_up(keycode, keystate):
    global currentMod
    __inject(keycode, UP)
    currentMod = ''

def inject_mod_down(keycode, keystate):
    __inject(keycode, DOWN)

def matchMod(keycode):
    global currentMod
    result = keycode in KEY_MAP.keys()
    if result:
        currentMod = keycode
    return result

def judge_mod_down(keycode, keystate):
    return matchMod(keycode) and keystate == DOWN

def judge_mod_up(keycode, keystate):
    return matchMod(keycode) and keystate == UP

def judge_else(keycode, keystate):
    return True

def judge_key(keycode, keystate):
    global currentMod
    mod = KEY_MAP.get(currentMod)
    return mod and (keycode in mod.keys())

def mapped (keycode, keystate):
    global currentMod
    mapKeys = KEY_MAP.get(currentMod).get(keycode)
    for mapKey in mapKeys:
        __inject(mapKey, keystate)

def inject(keycode, keystate):
    __inject(keycode, keystate)

STATE_MAP = {
    NORMAL: [
        State(judge_mod_down, MOD), 
        State(judge_else, NORMAL, [inject])
    ],
    MOD: [
        State(judge_key, MAPPED, [mapped]),
        State(judge_mod_up, NORMAL, [inject_mod_down, inject_mod_up]),
        State(judge_else, INJECT, [inject_mod_down, inject])
    ],
    INJECT: [
        State(judge_key, MAPPED, [inject_mod_up, mapped]),
        State(judge_mod_up, NORMAL, [inject_mod_up]),
        State(judge_else, INJECT, [inject])
    ],
    MAPPED: [
        State(judge_key, MAPPED, [mapped]),
        State(judge_mod_up, NORMAL),
        State(judge_else, INJECT, [inject_mod_down, inject])
    ]
}

def handle (ks):
    global currentState

    if not ks.finished():
        return

    currentStateOptions = STATE_MAP.get(currentState)
    for item in currentStateOptions:
        if item.judge(ks.keycode, ks.keystate):
            currentState = item.nextState
            logState.append(currentState)
            for act in item.action:
                act(ks.keycode, ks.keystate)
            break

    ks.reset()

dev = evdev.InputDevice('/dev/input/event3')
ui = evdev.UInput()

def main():
    global dev
    global ui

    ks = keystroke()

    dev.grab()

    for event in dev.read_loop():
        kev = evdev.categorize(event)
        ks.input(kev)

        handle(ks)

    dev.ungrab()

    dev.close()
    ui.close()

if __name__ == "__main__":
    main()
