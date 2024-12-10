def look(a, agent, -):
    """
    look action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.

    Preconditions:
        and
(atLocation ?a ?l)

    Effects:
        and
(checked ?l)
)
    """
    pass

def inventory(a, agent):
    """
    inventory action.

    Parameters:
        a (-): Description of ?a.

    Preconditions:
        None

    Effects:
        and
(checked ?a)
)
    """
    pass

def examineReceptacle(a, agent, -):
    """
    examineReceptacle action.

    Parameters:
        a (-): Description of ?a.
        agent (?r): Description of agent.
        - (receptacle): Description of -.

    Preconditions:
        and
(exists (?l - location)
(and
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
)
)

    Effects:
        and
(checked ?r)
)
    """
    pass

def examineObject(a, agent, -):
    """
    examineObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?o): Description of agent.
        - (object): Description of -.

    Preconditions:
        or
;(exists (?l - location)
;    (and
;        (atLocation ?a ?l)
;        (objectAtLocation ?o ?l)
;    )
;)
(exists (?l - location, ?r - receptacle)
(and
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
; (objectAtLocation ?o ?l)
(inReceptacle ?o ?r)
(or (not (openable ?r)) (opened ?r))  ; receptacle is opened if it is openable.
)
)
(holds ?a ?o)

    Effects:
        and
(checked ?o)
)
    """
    pass

def GotoLocation(a, agent, -, lEnd, location, -):
    """
    GotoLocation action.

    Parameters:
        a (-): Description of ?a.
        agent (?lStart): Description of agent.
        - (location): Description of -.
        lEnd (-): Description of ?lEnd.
        location (?r): Description of location.
        - (receptacle): Description of -.

    Preconditions:
        and
(atLocation ?a ?lStart)
(receptacleAtLocation ?r ?lEnd)
;(exists (?r - receptacle) (receptacleAtLocation ?r ?lEnd))

    Effects:
        and
(not (atLocation ?a ?lStart))
(atLocation ?a ?lEnd)
; (forall (?r - receptacle)
;     (when (and (receptacleAtLocation ?r ?lEnd)
;                (or (not (openable ?r)) (opened ?r)))
;         (checked ?r)
;     )
; )
; (increase (total-cost) (distance ?lStart ?lEnd))
(increase (total-cost) 1)
)
    """
    pass

def OpenObject(a, agent, -, r, receptacle):
    """
    OpenObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        r (-): Description of ?r.

    Preconditions:
        and
(openable ?r)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(not (opened ?r))

    Effects:
        and
(opened ?r)
(checked ?r)
(increase (total-cost) 1)
)
    """
    pass

def CloseObject(a, agent, -, r, receptacle):
    """
    CloseObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        r (-): Description of ?r.

    Preconditions:
        and
(openable ?r)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(opened ?r)

    Effects:
        and
(not (opened ?r))
(increase (total-cost) 1)
)
    """
    pass

def PickupObject(a, agent, -, o, object, -):
    """
    PickupObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        o (-): Description of ?o.
        object (?r): Description of object.
        - (receptacle): Description of -.

    Preconditions:
        and
(pickupable ?o)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
; (objectAtLocation ?o ?l)
(inReceptacle ?o ?r)
(not (holdsAny ?a))  ; agent's hands are empty.
;(not (holdsAnyReceptacleObject ?a))
(or (not (openable ?r)) (opened ?r))  ; receptacle is opened if it is openable.
;(not (isReceptacleObject ?o))

    Effects:
        and
(not (inReceptacle ?o ?r))
(holds ?a ?o)
(holdsAny ?a)
(not (objectAtLocation ?o ?l))
;(not (full ?r))
(increase (total-cost) 1)
)
    """
    pass

def PutObject(a, agent, -, o, object, -, ot, otype, -):
    """
    PutObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        o (-): Description of ?o.
        object (?r): Description of object.
        - (receptacle): Description of -.
        ot (-): Description of ?ot.
        otype (?rt): Description of otype.
        - (rtype): Description of -.

    Preconditions:
        and
(holds ?a ?o)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(or (not (openable ?r)) (opened ?r))    ; receptacle is opened if it is openable
;(not (full ?r))
(objectType ?o ?ot)
(receptacleType ?r ?rt)
(canContain ?rt ?ot)
;(not (holdsAnyReceptacleObject ?a))

    Effects:
        and
(inReceptacle ?o ?r)
(objectAtLocation ?o ?l)
;(full ?r)
(not (holds ?a ?o))
(not (holdsAny ?a))
(increase (total-cost) 1)
)
    """
    pass

def CleanObject(a, agent, -, r, receptacle, -):
    """
    CleanObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        r (-): Description of ?r.
        receptacle (?o): Description of receptacle.
        - (object): Description of -.

    Preconditions:
        and
(cleanable ?o)
(or
;(receptacleType ?r SinkType)
(receptacleType ?r SinkBasinType)
)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(holds ?a ?o)

    Effects:
        and
(increase (total-cost) 5)
(isClean ?o)
)
    """
    pass

def HeatObject(a, agent, -, r, receptacle, -):
    """
    HeatObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        r (-): Description of ?r.
        receptacle (?o): Description of receptacle.
        - (object): Description of -.

    Preconditions:
        and
(heatable ?o)
(or
(receptacleType ?r MicrowaveType)
)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(holds ?a ?o)

    Effects:
        and
(increase (total-cost) 5)
(isHot ?o)
(not (isCool ?o))
)
    """
    pass

def CoolObject(a, agent, -, r, receptacle, -):
    """
    CoolObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        r (-): Description of ?r.
        receptacle (?o): Description of receptacle.
        - (object): Description of -.

    Preconditions:
        and
(coolable ?o)
(or
(receptacleType ?r FridgeType)
)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(holds ?a ?o)

    Effects:
        and
(increase (total-cost) 5)
(isCool ?o)
(not (isHot ?o))
)
    """
    pass

def ToggleObject(a, agent, -, o, object, -):
    """
    ToggleObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        o (-): Description of ?o.
        object (?r): Description of object.
        - (receptacle): Description of -.

    Preconditions:
        and
(toggleable ?o)
(atLocation ?a ?l)
(receptacleAtLocation ?r ?l)
(inReceptacle ?o ?r)

    Effects:
        and
(increase (total-cost) 5)
(when (isOn ?o)
(not (isOn ?o)))
(when (not (isOn ?o))
(isOn ?o))
(isToggled ?o)
)
    """
    pass

def SliceObject(a, agent, -, co, object, -):
    """
    SliceObject action.

    Parameters:
        a (-): Description of ?a.
        agent (?l): Description of agent.
        - (location): Description of -.
        co (-): Description of ?co.
        object (?ko): Description of object.
        - (object): Description of -.

    Preconditions:
        and
(sliceable ?co)
(or
(objectType ?ko KnifeType)
(objectType ?ko ButterKnifeType)
)
(atLocation ?a ?l)
(objectAtLocation ?co ?l)
(holds ?a ?ko)

    Effects:
        and
(increase (total-cost) 5)
(isSliced ?co)
)
    """
    pass

def help(a, agent):
    """
    help action.

    Parameters:
        a (-): Description of ?a.

    Preconditions:
        None

    Effects:
        and
(checked ?a)
)
    """
    pass

