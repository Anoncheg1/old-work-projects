import os
import subprocess
import re
DELAY = 1


class MyException(Exception):
    """Base class for other exceptions"""
    def __init__(self, message):
        super().__init__(message)


def find_out_channels_count(filepath):
    pr = subprocess.Popen(['ffprobe', '-i', filepath, '-show_streams'], shell=False, stdout=subprocess.PIPE)
    pr.wait(DELAY)  # may throw subprocess.TimeoutExpired
    if pr.wait() != 0:
        raise MyException("Fail to get info about file " + os.path.basename(filepath))
    r1 = [x.decode('utf-8') for x in pr.stdout.readlines()]
    r2 = [x for x in r1 if x == 'channels=2\n' or x == 'channel_layout=stereo\n']
    # pr.kill()
    pr.terminate()
    if len(r2) > 0:  # stereo
        return 2
    else:
        return 1


def split_stereo_file(filepath, tmpdir) -> (str, str or None):
    """ return filepathleft, filepathright"""
    fpl = os.path.join(tmpdir, "left.wav")
    fpr = os.path.join(tmpdir, "right.wav")
    channels_count = find_out_channels_count(filepath)
    if channels_count == 2:  # stereo
        pr = subprocess.Popen(["ffmpeg", "-i", filepath, "-map_channel", "0.0.0",
                           fpl, "-map_channel", "0.0.1", fpr], shell=False)
        pr.wait(DELAY)  # may throw subprocess.TimeoutExpired
        if pr.wait() != 0:
            raise MyException("Fail to split file " + os.path.basename(filepath))
        return fpl, fpr
    elif channels_count == 1:  # mono or surround
        # r3 = [x for x in r1 if x == 'channels=1' or x == 'channel_layout=mono']
        # if len(r3) == 2:  # mono
        return filepath, None
    else:
        raise MyException("Unknown channels count in " + os.path.basename(filepath))


def filter_stable_ts(result, precision=2):
    """start,end,text,word_timestamps=[]"""
    s_l = []
    for s in result['segments']:
        snew = {key: value for key, value in s.items() if
             key in ['text', 'start', 'end', 'whole_word_timestamps']}
        # -- renaming and round
        snew['begin'] = round(snew['start'], precision)
        del snew['start']
        snew['end'] = round(snew['end'], precision)
        # -- add avg_confidence
        if s['whole_word_timestamps'] is None:
            snew['avg_confidence'] = 0
        else:
            confidences = [x['confidence'] for x in s['whole_word_timestamps'] if x is not None]
            snew['avg_confidence'] = round(sum(confidences)/len(confidences), precision)
        # -- sorting
        snew = dict(sorted(snew.items()))
        # --
        snew['words'] = [{key: value for key, value in w.items() if key in ['word', 'timestamp', 'confidence']}
                                         for w in snew['whole_word_timestamps']]
        for x in snew['words']:
            x['timestamp'] = round(x['timestamp'], precision)
            x['confidence'] = round(x['confidence'], precision)
        snew['text'] = snew['text'].encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
        for x in snew['words']:
            x['word'] = x['word'].encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
        del snew['whole_word_timestamps']
        s_l.append(snew)
    return s_l


def mix_channels(ch1: list or None, ch2: list = None) -> list:
    """ Convert from fromat of {'channel1':[], 'channel1':[]}
    to format [{'channel':1}, {'channel':1}, {'channel':2}]
    Side effect on ch1, ch2 """
    if ch2 is None or len(ch2) == 0:
        for x in ch1:
            x['channel'] = 1
        assert len([x for x in ch1 if 'channel' in x.keys()]) == len(ch1)
        return ch1
    elif ch1 is None or len(ch1) == 0:
        for x in ch2:
            x['channel'] = 2
        assert len([x for x in ch2 if 'channel' in x.keys()]) == len(ch2)
        return ch2
    i1 = 0
    i2 = 0
    l1 = len(ch1)
    l2 = len(ch2)
    mix = []
    while True:
        s1 = ch1[i1]
        s2 = ch2[i2]
        if s1['begin'] <= s2['begin']:
            s1['channel'] = 1
            mix.append(s1)
            i1 += 1
        else:
            s2['channel'] = 2
            mix.append(s2)
            i2 += 1
        # -- if the end is reached
        if i1 >= l1 and i2 < l2:
            for x in ch2[i2:]:
                x['channel'] = 2
                mix.append(x)
            break
        elif i2 >= l2 and i1 < l1:
            for x in ch1[i1:]:
                x['channel'] = 1
                mix.append(x)
            break
        elif i1 >= l1 and i2 >= l2:
            break
    assert len([x for x in mix if 'channel' in x.keys()]) == len(mix)
    return mix


def mix_channels_readable(ch1: list or None, ch2: list = None) -> list:
    """ Convert from  {'channel1':[], 'channel1':[]}
    to format [{'channel':1}, {'channel':1}, {'channel':2}]
    Side effect on ch1, ch2 """
    # print('ch1', ch1)
    # print('ch2', ch2)
    mixed = mix_channels(ch1, ch2)
    # print(mixed)
    mix = []
    for x in mixed:
        # print(x)
        if x['channel'] == 1:
            mix.append({'channel 1': x["text"].strip()})
        else:
            mix.append({'channel 2': x["text"].strip()})
    return mix


# def get_sentences(ch):
#     """ ch is transcribe response for one channel"""
#     if ch is None or len(ch) == 0:
#         return None
#     else:
#         return [s['text'] for s in ch]


def get_sentences_for_encoding(sentences: list):
    """ carefully split sentences by the .?! chars
    sentences = [s['text'] for s in ch]"""

    concat_flag = False

    sentences_careful = []
    for sen in sentences:
        sen = sen.strip()
        # print("sen", sen)
        # sen = 'asda. asdasd? asd.'
        matches = re.finditer(r'[.!?]', sen)
        matches = list(matches)
        # print(matches, sen, len(sen), matches[0].group())
        if len(matches) == 0:
            if concat_flag is True:
                sentences_careful[-1] = sentences_careful[-1] + ' ' + sen.strip()
            else:
                sentences_careful.append(sen)
            if sentences_careful[-1][-1] not in '.!?':
                concat_flag = True
            continue

        # print(list(matches))
        # sp = [sen]
        sss = []
        b = None
        for m in matches:
            if b is None:
                sss.append(sen[:m.end()])
            else:
                sss.append(sen[b.end():m.end()])
            b = m
        # print("sentences_careful", sentences_careful)
        # print("sss", sss)
        if concat_flag is True:
            sentences_careful[-1] = sentences_careful[-1] + ' ' + sss[0].strip()
            sentences_careful.extend(sss[1:])
        else:
            sentences_careful.extend(sss)
        # print(sss)
        # exit()
        # print(sentences_careful)
        if sentences_careful[-1][-1] not in '.!?':
            concat_flag = True
        else:
            concat_flag = False
        sentences_careful = [x.strip() for x in sentences_careful]
    return sentences_careful