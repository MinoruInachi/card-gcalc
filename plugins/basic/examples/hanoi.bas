' Tower of Hanoi: a recursive SUB
moves = 0
SUB hanoi(n, from$, to$, via$)
  IF n = 0 THEN EXIT SUB
  hanoi n - 1, from$, via$, to$
  moves = moves + 1
  IF n >= 3 THEN PRINT "disk "; n; ": "; from$; " -> "; to$
  hanoi n - 1, via$, to$, from$
END SUB

hanoi 4, "A", "C", "B"
PRINT moves; " moves"
