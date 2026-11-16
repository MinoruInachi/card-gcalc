' Graphics: shapes, then a bouncing ball (any key stops)
GCLS
FOR i = 0 TO 11
  CIRCLE 120, 67, 5 + i * 5, RGB(255 - i * 20, 80 + i * 14, 120)
NEXT
FOR x = 0 TO 239 STEP 12
  LINE x, 134, 239 - x, 0, RGB(40, 90 + x \ 3, 200)
NEXT
BOX 70, 55, 100, 24, "black", 1
GPRINT 84, 62, "card-gcalc BASIC", "yellow"
k$ = WAITKEY$

x = 20: y = 20: dx = 3: dy = 2
DO
  GCLS
  CIRCLE x, y, 6, "orange", 1
  GPRINT 2, 2, "any key: stop", "gray"
  SLEEP 0.02
  x = x + dx: y = y + dy
  IF x < 6 OR x > 233 THEN dx = -dx
  IF y < 6 OR y > 128 THEN dy = -dy
LOOP WHILE INKEY$ = ""
