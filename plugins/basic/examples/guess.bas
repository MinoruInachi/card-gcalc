' Number guessing game: SELECT CASE and DO ... LOOP
RANDOMIZE
secret = INT(RND * 100) + 1
tries = 0
PRINT "I am thinking of a number 1-100."
DO
  INPUT "Guess"; g
  tries = tries + 1
  SELECT CASE g
    CASE IS < secret
      PRINT "Higher"
    CASE IS > secret
      PRINT "Lower"
    CASE ELSE
      PRINT "Correct in "; tries; " tries!"
      EXIT DO
  END SELECT
LOOP
