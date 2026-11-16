' Prime numbers with a FUNCTION
FUNCTION isprime(n)
  LOCAL d
  IF n < 2 THEN RETURN 0
  d = 2
  WHILE d * d <= n
    IF n MOD d = 0 THEN RETURN 0
    d = d + 1
  WEND
  RETURN -1
END FUNCTION

t = TICKS
count = 0
FOR n = 2 TO 500
  IF isprime(n) THEN
    count = count + 1
    IF n > 450 THEN PRINT n;" ";
  END IF
NEXT
PRINT
PRINT count; " primes below 500"
PRINT "time: "; TICKS - t; " ms"
