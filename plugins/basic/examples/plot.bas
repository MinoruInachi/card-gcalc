' Plot y = sin(x) * exp(-x / 8) with axes
GCLS
LINE 0, 67, 239, 67, "gray"
LINE 10, 0, 10, 134, "gray"
FOR px = 10 TO 239
  x = (px - 10) / 10
  y = SIN(x) * EXP(-x / 8)
  PSET px, 67 - y * 55, "yellow"
NEXT
GPRINT 140, 4, "sin(x)*exp(-x/8)", "cyan"
