#coding:utf-8
import sys
from modelFiles import modelFilesList
import simplejson as json
from gensim import models
import time
import random
import operator
import numpy
reload(sys)
sys.setdefaultencoding('utf8')

class Poem:
    def __init__(self):
        self._important_words = []
        self._title = ""
        self._search_ratio = 0

        self.title2pingze = {}
        self.title2delimiter = {}
        self.pingze2rhythm = {}
        self.word2rhythm = {}
        self.pingze2word = {}
        self.rhythm2word = {}
        self.word2pingze = {}
        self.lastWordCount = {}
        self.lastRhythmCount = {}
        self.bigramCount = {}
        self.bigramStart = {}
        self.bigramEnd = {}

        self.bigramWord2VecModel = None
        self.trigramWord2VecModel = None

        self.sentences = []

    def loadModel(self):
        for data_file in modelFilesList:
            with open("./model/"+data_file, "r") as f:
                value = json.load(f)
                setattr(self, data_file, value)
        self.bigramWord2VecModel = models.Word2Vec.load("./model/bigramWordModel")
        self.trigramWord2VecModel = models.Word2Vec.load("./model/trigramWordModel")


    def format(self, result_sentence_list):
        l = []
        result = ""
        delimiters = self.title2delimiter[self._title]
        index = 0
        for result_sentence in result_sentence_list:
            result += result_sentence
            result += delimiters[index]
            if (index+1 < len(delimiters)) and (delimiters[index+1] == "|"):
                l.append(result)
                result = ""
                index += 1
            index += 1
        l.append(result)
        return l

    def getSegmentation(self, pingzeSentence):
        length = len(pingzeSentence)
        if length == 2 or length == 3:
            return [pingzeSentence]
        elif length == 4 or length == 5:
            return [pingzeSentence[0:2], pingzeSentence[2:]]
        elif length == 6 or length == 7:
            return [pingzeSentence[0:2], pingzeSentence[2:4], pingzeSentence[4:]]
        elif length == 9:
            return [pingzeSentence[0:2], pingzeSentence[2:4], pingzeSentence[4:6], pingzeSentence[6:]]

    def checkPingzeAndWord(self, pingze, keyWord):
        if len(pingze) != len(keyWord):
            return False
        for i in range(0, len(keyWord)):
            if pingze[i] == '0':
                continue
            if keyWord[i] in self.word2pingze and self.word2pingze[keyWord[i]] != pingze[i]:
                return False
        return True


    def findTrigram(self, pingze, keyWord, usedWord):
        try:
            candidateWords = self.trigramWord2VecModel.most_similar(positive=[keyWord], topn=100)
        except KeyError as e:
            #print "Cannot find " + keyWord
            return ""

        candidateWords = sorted(candidateWords, key=operator.itemgetter(1), reverse=True)
        tmpRes = ""
        for word in candidateWords:
            w =word[0]
            if len(w) == 3:
                if self.checkPingzeAndWord(pingze, w):
                    if w in usedWord:
                        continue
                    return w
                elif tmpRes == "":
                    tmpRes = w
        return tmpRes

    def fill(self, i, keyWord, segment, usedWord, direction=1):
        curIndex = i + direction
        if curIndex < 0 or curIndex >= len(segment):
            return ""
        res = ""
        if len(segment[curIndex]) == 3:
            # find trigram using keyWord
            res = self.findTrigram(segment[curIndex], keyWord, usedWord)
            return res

        candidateWords = self.bigramWord2VecModel.most_similar(positive=[keyWord], topn=100)
        candidateWords = sorted(candidateWords, key=operator.itemgetter(1), reverse=True)
        for candidateWord in candidateWords:
            newWord = candidateWord[0]
            if newWord in usedWord:
                continue
            if self.checkPingzeAndWord(segment[curIndex], newWord):
                res = newWord
                remaining = self.fill(curIndex, newWord, segment, usedWord, direction)
                if remaining != False:
                    if direction == 1:
                        res += remaining
                    else:
                        res = remaining + res
                    return res

    def generateSentence(self, pingzeSentence, keyWord, usedWord, ForceBuild=False):
        segment = self.getSegmentation(pingzeSentence)
        # Flase: this sentence is gennerated without using keywords
        # True: this sentence is gennerated using this keywords
        flag = False
        for i in range(len(segment)):
            result = ""
            if len(segment[i]) == 3 and i == 0:
                result = self.findTrigram(segment[i], keyWord, usedWord)
                flag = False
            elif self.checkPingzeAndWord(segment[i], keyWord) or ForceBuild:
                result = keyWord
                front = self.fill(i, keyWord, segment, usedWord, direction=-1)
                if front == False:
                    continue
                back = self.fill(i, keyWord, segment, usedWord, direction=1)
                if back == False:
                    continue
                result = front + result + back
                flag = True
                break
        return result, flag

    def segment(self, sentence):
        length = len(sentence)
        res = []
        if length == 2 or length == 3:
            res.append(sentence)
        elif length == 4 or length == 5:
            res.append(sentence[0:2])
            res.append(sentence[2:])
        elif length == 6 or length == 7:
            res.append(sentence[0:2])
            res.append(sentence[2:4])
            res.append(sentence[4:])
        elif length == 9:
            res.append(sentence[0:2])
            res.append(sentence[2:4])
            res.append(sentence[4:6])
            res.append(sentence[6:])
        return res

    def write(self):
        if self._title not in self.title2pingze:
            raise ValueError("title[%s] not defined in dict" % self._title)
        pingzeSentences = self.title2pingze[self._title]

        result = []
        usedWord = []
        j = 0
        for i in range(len(pingzeSentences)):
            # generate ith sentence
            pingzeSentence = pingzeSentences[i]
            keyWordList = self._important_words[j]
            failTimes = 0;
            for keyWord in keyWordList:
                # try to generate ith sentence using keyWord
                if keyWord in usedWord:
                    continue
                sentence, flag = self.generateSentence(pingzeSentence, keyWord, usedWord)
                if not sentence:
                    failTimes += 1
                    if failTimes == len(keyWordList):
                        sentence, flag = self.generateSentence(pingzeSentence, keyWordList[0], usedWord, ForceBuild=True)
                    else:
                        continue
                result.append(sentence)
                usedWord.extend(self.segment(sentence))
                if flag:
                    j += 1
                break
        return self.format(result)

def getUserInput():
    tags = []
    length = len(sys.argv)
    for tag in range(1, length):
        tags.append(tag)
    print tags

def checkValid(key, userKey):
    for keyElment in userKey:
        if keyElment in key:
            return True
    return False

def getTopNKeyWords(poem, used, count = 20):
    candidate = []
    for word in poem.bigramCount:
        if word[0] in used:
            continue
        if random.random() > 0.5:
            candidate.append(word[0])
            used.append(word[0])
            if len(candidate) == count:
                break;
    return candidate

def extendKeyWords(keyWords, poem):
    candidateLength = 20
    res = {}
    length = len(poem.title2pingze[poem._title])
    used = []
    finished = 0;
    for key, count in poem.bigramCount:
        for i in range(len(keyWords)):
            if i in res and len(res[i]) >= candidateLength:
                continue
            if(checkValid(key, keyWords[i]) and key not in used):
                if random.random() > 0.1:
                    candidate = []
                    if i in res:
                        candidate = res[i]
                    if(key == keyWords[i]):
                        candidate.insert(0, key)
                    else:
                        candidate.append(key)
                    used.append(key)
                    res[i] = candidate
                    if len(candidate) == candidateLength:
                        finished += 1
        if finished == len(keyWords):
            break

    for i in range(length):
        if i in res:
            continue
        res[i] = getTopNKeyWords(poem, used, candidateLength)
    return res

if __name__ == '__main__':
    # titleList = [u"蝶恋花", u"风入松", u"摸鱼儿"]
    poem = Poem()

    begin = time.time()
    poem.loadModel()
    end = time.time()
    print "finish building model, using " + str(end - begin) + "seconds"
    titleList = poem.title2pingze.keys()
    #tags = getUserInput()
    tags = ["春风", "明月", "江南", "笑"]

    for title in titleList:
        #print "write " + title
        poem._title = title
        words = []
        for tag in tags:
            words.append(tag.decode())
        words = extendKeyWords(words, poem)
        #numpy.random.shuffle(words)
        poem._important_words = words
        result = poem.write()
        print poem._title
        print result[0]
        print result[1]
        print "\n"
