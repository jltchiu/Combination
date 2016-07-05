# System Combination

This is the script used for System Combination reported in the work: "Features for Search and Understanding ofNoisy Conversational Speech"


```
USAGE: syscomb.py <language code> <corpus (dev|eval)> <kwlist id (dev|eval)>
                  <method> <output path> <input files> [--weights <weights>]
     * <method> can be one of the following:
       # MAX: final score = maximum score of the detections
       # MIN: final score = minimum score of the detections
       # MED: final score = median score of the detections
       # SUM: final score = sum(score * weight) of the detections
       # MNZ: final score = sum(score * weight) * sum(weight) of the detections
       # ANZ: final score = sum(score * weight) / sum(weight) of the detections
                            (weighted average of the scores)
     * <output path>: Two detection lists will be written to this path:
       # kwslist.raw.xml: With unnormalized scores;
       # kwslist.xml    : With normalized scores, ready for scoring.
     * <input files>: Specify the input detection lists. You can supply
       detection lists with either unnormalized or normalized scores.
       Wildcards are accepted.
     * <weights>: Specify weights for each detection list. There must be exactly
       as many weights as input files. If not given, defaults to all ones.
```
