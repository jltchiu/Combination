import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))
import codecs
import os
import re
import types
from config import *
from KwList import *
from DetList import *

USAGE = r"""
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
"""

def combMAX(scores, weights):   # weights are irrelevant
    return max(scores)

def combMIN(scores, weights):   # weights are irrelevant
    return min(scores)

def combMED(scores, weights):   # weights are irrelevant
    scores = sorted(scores)
    n = len(scores)
    if n % 2 == 1:
        return scores[n/2]
    else:
        return (scores[n/2-1] + scores[n/2]) / 2.0

def combSUM(scores, weights):
    return sum(scores[i] * weights[i] for i in range(len(scores)))

def combMNZ(scores, weights):
    return sum(scores[i] * weights[i] for i in range(len(scores))) * sum(weights)

def combANZ(scores, weights):
    return sum(scores[i] * weights[i] for i in range(len(scores))) / sum(weights)

if __name__ == "__main__":
    # Parse input arguments
    try:
        LANGUAGE_CODE   = sys.argv[1]
        CORPUS          = sys.argv[2]
        KWLIST_ID       = sys.argv[3]
        METHOD          = sys.argv[4]
        COMB_FUNC       = "comb" + METHOD.upper()
        if COMB_FUNC not in globals() or type(globals()[COMB_FUNC]) != types.FunctionType:
            raise Exception("Unsupported method: " + METHOD)
        COMB_FUNC       = globals()[COMB_FUNC]
        RESULT_PATH     = os.path.abspath(sys.argv[5])
        p = [i for i in range(6, len(sys.argv)) if re.match(r'^--?weights?$', sys.argv[i])]
                                                # Let's have some tolerance here
        p = p[0] if len(p) > 0 else len(sys.argv)
        INPUT_FILES     = sys.argv[6:p]
        N = len(INPUT_FILES)
        if p < len(sys.argv):
            WEIGHTS     = [float(w) for w in sys.argv[p+1:]]
            if len(WEIGHTS) != N:
                raise Exception("Number of weights (%d) doesn't match number of input files (%d)." %
                                (len(WEIGHTS), N))
        else:
            WEIGHTS     = [1 for x in INPUT_FILES]
    except Exception as e:
        if len(sys.argv) > 1:
            if type(e) == IndexError:
                sys.stderr.write("Not enough input arguments.\n")
            elif type(e) == ValueError:
                sys.stderr.write("Incorrect form of weight provided: \"" + e.message[e.message.index(":")+2:] + "\".\n")
            else:
                sys.stderr.write(e.message + "\n")
        sys.stderr.write(USAGE)
        sys.exit(1)

    # Configurations
    globals().update(config(LANGUAGE_CODE, CORPUS, KWLIST_ID))
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout)
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr)

    # Load keyword list and build result detection list
    kwlist = parseKwList(KWLIST_FILE)
    outList = DetList(kwlist)
    outList.kwlistFilename = os.path.basename(KWLIST_FILE)
    outList.language = LANGUAGE
    
    # Load input detection lists
    inLists = []
    for i in range(N):
        sys.stderr.write("Loading input detection list %s (weight = %.6f) ...\n" % (INPUT_FILES[i], WEIGHTS[i]))
        inLists.append(DetList(kwlist))
        inLists[-1].readXml(INPUT_FILES[i], removeZeroScore = True)

    # Combine input detection lists
    sys.stderr.write("Combining input detection lists ...\n")
    detKey = lambda x: (x.filename, x.startTime, x.endTime) # Key for comparing detections
    for kw in kwlist:
        L = [inList[kw.id] for inList in inLists]
        for i in range(N):
            L[i].sort(key = detKey, reverse = True)
            for det in L[i]:
                det.weight = WEIGHTS[i]
        maxScore = 0
        while any(len(l) > 0 for l in L):
            # Find the "minimum" detection
            head = min([l[-1] for l in L if len(l) > 0], key = detKey)
            filename = head.filename
            endTime = head.endTime
            # Find all detections that can be merged with head
            candidates = []
            flag = True
            while flag:
                flag = False
                for i in range(N):
                    if len(L[i]) > 0:
                        if L[i][-1].filename == filename and L[i][-1].startTime < endTime:
                            if L[i][-1].endTime > endTime: endTime = L[i][-1].endTime
                            candidates.append(L[i][-1])
                            del L[i][-1]
                            flag = True
            # Merge the candidates into a single detection and put it into outList
            # Start and end times are weighted averages of original values,
            #   weighted by score * weight
            # Scores are combined as specified by METHOD
            w         = sum(det.score * det.weight for det in candidates)
            startTime = sum(det.startTime * det.score * det.weight for det in candidates) / w
            endTime   = sum(det.endTime   * det.score * det.weight for det in candidates) / w
            score     = COMB_FUNC([det.score for det in candidates], [det.weight for det in candidates])
            if score > maxScore: maxScore = score
            outList[kw.id].append(Detection(filename, startTime, endTime, score))
        if maxScore > 1:
            for det in outList[kw.id]:
                det.score /= maxScore

    # Make decisions
    outList.makeDecisions(BETA, TOTAL_DURATION, POSTERIOR_BOOST * 1.4)

    # Write out the detection list
    sys.stderr.write("Writing output detection lists ...\n")
    if not os.path.exists(RESULT_PATH): os.makedirs(RESULT_PATH)
    outList.writeXml(os.path.join(RESULT_PATH, "kwslist.raw.xml"), normalize = False)
    outList.writeXml(os.path.join(RESULT_PATH, "kwslist.xml"), normalize = True)

    sys.stderr.write("Done!\n")
