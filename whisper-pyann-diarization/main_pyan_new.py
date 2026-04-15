import sys
import tempfile
# print(sys.argv[1])
# exit()
# for file in *.wav ; do python3 main_pyan.py > ${file}.txt ; done
import string

import numpy as np

import stable_whisper as whisper

from pyannote.audio import Pipeline

from pyannote.core import Segment

# import tensorflow_hub as hub

import tensorflow as tf

import tensorflow_text

import nltk

from nltk.corpus import stopwords

from nltk.probability import FreqDist

import pymorphy3

# from sklearn.metrics import jaccard_score

# from sklearn.feature_extraction.text import CountVectorizer

from fuzzywuzzy import fuzz

# import fasttext

# from sklearn.metrics.pairwise import cosine_similarity

import time
# own
from utils import split_stereo_file, find_out_channels_count

queries = [

    "Добрый день, могу я услышать?",

    "Звонок из «РУСНАРБАНКа» Меня зовут",

    "Вы оставляли Заявку на автокредит? ",

    "Актуальна ли для Вас заявка?",

    "Еще рассматриваете вопрос о приобретении автомобиля?",

    "Удобно будет сверить сейчас данные по анкете?",

    "Вам сейчас удобно разговаривать?",

    "Вы можете уделить время для проверки данных по анкете?",

    "Информируем Вас о том, что ведется запись телефонных переговоров",

    "Назовите Ваши ФИО, дату рождения и количество полных лет?",

    "По какому адресу зарегистрированы и проживаете?",

    "Состоите ли в барке?",

    "Назовите ФИО и дату рождения супруги",

    "Какой автомобиль планируете приобрести? (марка, модель, год выпуска)",

    "стоимость выбранного ТС и первоначальный взнос?",

    "Трудоустроены ли Вы на данный момент?",

    "Как называется организация, в которой Вы работаете? Уточните, пожалуйста, должность и уровень заработной платы.",

    "Сможете ли Вы оплачивать по кредитным обязательствам в полном объеме с учетом сложившейся экономической ситуации в стране?",

    "Чьи контактные данные оставляли в анкете?",
]


def diarize_text(transcribe, diarization):
    timestamp_texts = []

    fin_result = whisper.text_output.finalize_segment_word_ts(transcribe, combine_compound=True)

    for item in fin_result:

        sentence = ''.join([it for it in item[0]])

        start = item[1][0]['start']

        end = item[1][-1]['end']

        spk = diarization.crop(Segment(start, end)).argmax()

        words = []

        for it in zip(item[0], item[1]):
            words.append((it[0], it[1]['start'], it[1]['end']))

        timestamp_texts.append((Segment(start, end), spk, sentence, words))

    return timestamp_texts


def notdiarize_text(transcribe, spk):
    timestamp_texts = []

    fin_result = whisper.text_output.finalize_segment_word_ts(transcribe, combine_compound=True)

    for item in fin_result:

        sentence = ''.join([it for it in item[0]])

        start = item[1][0]['start']

        end = item[1][-1]['end']

        # spk = diarization.crop(Segment(start, end)).argmax()

        words = []

        for it in zip(item[0], item[1]):
            words.append((it[0], it[1]['start'], it[1]['end']))

        timestamp_texts.append((Segment(start, end), spk, sentence, words))

    return timestamp_texts

# --- load whisper
model = whisper.load_model("tiny")

options = dict(language="ru", beam_size=5,
               best_of=5)  # , prompt="Здравствуйте, я звоню из Руснарбанка, на кредит заявку рассматриваете?", prefix=None)

transcribe_options = dict(task="transcribe", **options)

# --- load diarizer
pipeline = Pipeline.from_pretrained("config_pyannote_diarization.yaml")
print("diarized loaded")
# --- load embedder


module_url = "/home/tt/universal-sentence-encoder-multilingual-large_3"
# embed = tf.saved_model.load(module_url)
# # ------- prepare ander-client detection
# queries_embedding = embed(queries)

# time.sleep(100)
print("embedder loaded")

# --- load morph normalizer
analyzer = pymorphy3.MorphAnalyzer()


def mono_diarize_transcribe(filepath):
    # ------------------ transcribe whisper

    asr_result = model.transcribe(filepath, language="ru") # **transcribe_options)

    # --------------- diarozi pyannote - [ 00:00:00.497 -->  00:00:00.683] AK SPEAKER_01
    diarization_result = pipeline(filepath, num_speakers=2)

    # -- get asr by diarization timestamps
    final_result = diarize_text(asr_result, diarization_result)
    embed = tf.saved_model.load(module_url)  # should be after all, because of picks in memory consumption
    queries_embedding = embed(queries)
    # nltk.download('punkt')

    # nltk.download('stopwords')

    stop_words = stopwords.words('russian')

    stop_words.extend(list(string.punctuation))

    # stop_words.extend(['что', 'это', 'так', ])

    # --------- convert queries to normal forms

    best_count = 10

    spk_query_score = {}

    spk_query_fdist = {}

    for seg, spk, sent, words in final_result:
        spk_s = str(spk)
        # seg - time
        # spk - speaker number (str)
        # sent - orig string
        # words - whisper words

        best_gusem = []

        best_fuzz = []

        if len(sent) > 10:

            # -- ! -- gusem

            scores = []

            # -- calc embed for sent
            # -- get best queries > 0.3 for sent
            sent_embedding = embed([sent])

            for query_embedding in queries_embedding:
                score = -tf.keras.losses.CosineSimilarity()(query_embedding, sent_embedding)

                scores.append(score)

            best_matches = np.argsort(scores)[-best_count:][::-1]  # ids of 10 top scores

            for i in best_matches:

                if scores[i] > 0.3:
                    best_gusem.append((scores[i].numpy(), queries[i], i))  # save queries and score if >0.3 score

            try:
                # -- per speaker collect best match score query
                spk_query_score[spk_s] += scores[best_matches[0]].numpy()

            except KeyError:

                spk_query_fdist[spk_s] = FreqDist()

                spk_query_score[spk_s] = scores[best_matches[0]].numpy()

            # -- ! -- nltk pymorphy - worlds only
            sent_nf = ' '.join([analyzer.parse(word)[0].normal_form for word in nltk.word_tokenize(sent) if
                                (analyzer.parse(word)[0].normal_form not in stop_words)])
            for word in nltk.tokenize.word_tokenize(sent_nf):
                spk_query_fdist[spk_s][word] += 1

            # fuzzywuzzy

            scores = []

            for query in queries:
                score = fuzz.token_set_ratio(sent, query)

                scores.append(score)

            best_matches = np.argsort(scores)  # [-best_count:][::-1]

            for i in best_matches:

                if scores[i] > 25:
                    best_fuzz.append((scores[i], queries[i], i))

            try:

                spk_query_score[spk_s + '_fuzz'] += scores[best_matches[0]]

            except KeyError:

                spk_query_score[spk_s + '_fuzz'] = scores[best_matches[0]]

        # line = f'************** {seg.start:.2f} {seg.end:.2f} {spk} {sent}'
        #
        # print(line)

    speaker0 = [v for x, v in spk_query_score.items() if x.startswith('SPEAKER_00')]
    speaker1 = [v for x, v in spk_query_score.items() if x.startswith('SPEAKER_01')]
    print(speaker0)
    print(speaker1)
    if len(speaker0) == 0 or len(speaker0) == 1:
        raise Exception("only one speaker in audio")
    speakers = np.array([speaker0, speaker1])
    speakers /= (speakers.max(axis=0) - 0)

    if np.sum(speakers[0] - speakers[1]) > 0:
        ander_spk = 'SPEAKER_00'
    else:
        ander_spk = 'SPEAKER_01'
    # print(ander_spk, 'is an operator')

    ander_words = []
    user_words = []
    for seg, spk, sent, words in final_result:
        print(seg, type(seg))
        exit()
        spk: str
        client_flag = True if spk is None or not spk.startswith(ander_spk) else False

        print('client:' if client_flag else 'operator:', sent)
        words_only = [x[0] for x in words]  # only worlds without timestamps

        if client_flag:
            user_words.extend(words_only)
        else:
            ander_words.extend(words_only)

    # print(ander_spk, 'is an operator')
    # print("Most common words:")
    most_common = {}
    for spk in spk_query_fdist:
        client_flag = True if spk is None or not spk.startswith(ander_spk) else False
        spk = 'client' if client_flag else 'operator'
        # print(spk, spk_query_fdist[spk].most_common(5))
        if spk in most_common.keys():
            most_common[spk].extend(spk_query_fdist[spk].most_common(5))
        else:
            most_common[spk] = spk_query_fdist[spk].most_common(5)


    return ander_words, user_words, most_common


def stereo_transcribe(filepath1, filepath2):
    # ------------------ transcribe whisper
    asr_result1 = model.transcribe(filepath1, **transcribe_options)
    asr_result2 = model.transcribe(filepath2, **transcribe_options)
    # -- get asr by diarization timestamps
    ander_spk = 'SPEAKER_00'
    user_spk = 'SPEAKER_01'
    # --
    final_result1 = notdiarize_text(asr_result1, ander_spk)
    final_result2 = notdiarize_text(asr_result2, user_spk)

    ander_words = []
    user_words = []

    for final_result in [final_result1, final_result2]:
        for seg, spk, sent, words in final_result:
            spk_s = str(spk)

            if len(sent) > 10:
                # -- ! -- nltk pymorphy - worlds only
                sent_nf = ' '.join([analyzer.parse(word)[0].normal_form for word in nltk.word_tokenize(sent) if
                                    (analyzer.parse(word)[0].normal_form not in stop_words)])
                for word in nltk.tokenize.word_tokenize(sent_nf):
                    spk_query_fdist[spk_s][word] += 1

        for seg, spk, sent, words in final_result:
            spk: str
            client_flag = True if spk is None or not spk.startswith(ander_spk) else False

            print('client:' if client_flag else 'operator:', sent)
            words_only = [x[0] for x in words]  # only worlds without timestamps

            if client_flag:
                user_words.extend(words_only)
            else:
                ander_words.extend(words_only)

    most_common = {}
    for spk in spk_query_fdist:
        client_flag = True if spk is None or not spk.startswith(ander_spk) else False
        spk = 'client' if client_flag else 'operator'
        # print(spk, spk_query_fdist[spk].most_common(5))
        if spk in most_common.keys():
            most_common[spk].extend(spk_query_fdist[spk].most_common(5))
        else:
            most_common[spk] = spk_query_fdist[spk].most_common(5)

    return ander_words, user_words, most_common



def output(ander_words, user_words):
    # -------------- load dictinaries
    from utils_dictionary import loads_dicts
    from utils_dictionary import find_by_dictionary
    dicts_vse = loads_dicts('/home/u2/Downloads/dictionaries/vse')
    dicts_operator = loads_dicts('/home/u2/Downloads/dictionaries/operator')
    dicts_client = loads_dicts('/home/u2/Downloads/dictionaries/client')

    # -------------- find by dictionary

    start_time = time.time()
    for k, v in dicts_vse.items():
        print("Dictionary:", k)
        print("In operator words:")
        find_by_dictionary(v, ander_words, embed)
        print()
        print("In client words:")
        find_by_dictionary(v, ander_words, embed)
        print()
    print()


    for k, v in dicts_operator.items():
        print("Dictionary:", k)
        print("In operator words:")
        find_by_dictionary(v, ander_words, embed)
        print()

    for k, v in dicts_client.items():
        print("Dictionary:", k)
        print("In client words:")
        find_by_dictionary(v, user_words, embed)
        print()
    print("Time: --- %s seconds ---" % (time.time() - start_time))


# ---------------- Main() -------------
filepath = '/home/tt/pyannotedobr/' + sys.argv[1]
start_time = time.time()
# -- count channels
channels_count = find_out_channels_count(filepath)
# -- detect speakers in stereo and mono
# tr1 and tr2 has speaker identity inside
if channels_count > 2:
    with tempfile.TemporaryDirectory() as tmpdir:
        ch1file, ch2file = split_stereo_file(filepath, tmpdir)
        if ch2file is not None:
            tr1, tr2, most_common = stereo_transcribe(ch1file, ch2file)
        else:
            tr1, tr2, most_common = mono_diarize_transcribe(filepath)
            if tr2 is None:
                raise Exception(f"No second speaker in {filepath}")
else:
    tr1, tr2, most_common = mono_diarize_transcribe(filepath)
# -- process speaker transcribe
res1 = one_channel_process(tr1)
res2 = one_channel_process(tr2)
output(res1, res2)

# ------------------ transcribe whisper
asr_result = model.transcribe(filepath, **transcribe_options)

# --------------- diarozi pyannote - [ 00:00:00.497 -->  00:00:00.683] AK SPEAKER_01
diarization_result = pipeline(filepath, num_speakers=2)
# -- get asr by diarization timestamps
final_result = diarize_text(asr_result, diarization_result)

# ------- prepare ander-client detection
module_url = "/home/tt/universal-sentence-encoder-multilingual-large_3"
# -- embedder
# embed = tf.saved_model.load(module_url)

queries_embedding = embed(queries)


analyzer = pymorphy3.MorphAnalyzer()

# nltk.download('punkt')

# nltk.download('stopwords')

stop_words = stopwords.words('russian')

stop_words.extend(list(string.punctuation))

# stop_words.extend(['что', 'это', 'так', ])

# --------- convert queries to normal forms
queries_nf = [' '.join([analyzer.parse(word)[0].normal_form for word in nltk.word_tokenize(query) if
                        (analyzer.parse(word)[0].normal_form not in stop_words)]) for query in queries]


best_count = 10

spk_query_score = {}

spk_query_fdist = {}

for seg, spk, sent, words in final_result:
    spk_s = str(spk)
    # seg - time
    # spk - speaker number (str)
    # sent - orig string
    # words - whisper words

    best_gusem = []

    best_nltk = []

    best_fuzz = []


    if len(sent) > 10:

        # -- ! -- gusem

        scores = []

        # -- calc embed for sent
        # -- get best queries > 0.3 for sent
        sent_embedding = embed([sent])

        for query_embedding in queries_embedding:
            score = -tf.keras.losses.CosineSimilarity()(query_embedding, sent_embedding)

            scores.append(score)

        best_matches = np.argsort(scores)[-best_count:][::-1]  # ids of 10 top scores

        for i in best_matches:

            if scores[i] > 0.3:
                best_gusem.append((scores[i].numpy(), queries[i], i))  # save queries and score if >0.3 score

        try:
            # -- per speaker collect best match score query
            spk_query_score[spk_s] += scores[best_matches[0]].numpy()

        except KeyError:

            spk_query_fdist[spk_s] = FreqDist()

            spk_query_score[spk_s] = scores[best_matches[0]].numpy()

        # -- ! -- nltk pymorphy - worlds only
        sent_nf = ' '.join([analyzer.parse(word)[0].normal_form for word in nltk.word_tokenize(sent) if
                            (analyzer.parse(word)[0].normal_form not in stop_words)])
        for word in nltk.tokenize.word_tokenize(sent_nf):
            spk_query_fdist[spk_s][word] += 1

        # fuzzywuzzy

        scores = []

        for query in queries:
            score = fuzz.token_set_ratio(sent, query)

            scores.append(score)

        best_matches = np.argsort(scores)  # [-best_count:][::-1]

        for i in best_matches:

            if scores[i] > 25:
                best_fuzz.append((scores[i], queries[i], i))

        try:

            spk_query_score[spk_s + '_fuzz'] += scores[best_matches[0]]

        except KeyError:

            spk_query_score[spk_s + '_fuzz'] = scores[best_matches[0]]

    # line = f'************** {seg.start:.2f} {seg.end:.2f} {spk} {sent}'
    #
    # print(line)

speaker0 = [v for x, v in spk_query_score.items() if x.startswith('SPEAKER_00')]
speaker1 = [v for x, v in spk_query_score.items() if x.startswith('SPEAKER_01')]
speakers = np.array([speaker0, speaker1])
speakers /= (speakers.max(axis=0) - 0)

if np.sum(speakers[0] - speakers[1]) > 0:
    ander_spk = 'SPEAKER_00'
else:
    ander_spk = 'SPEAKER_01'
print(ander_spk, 'is an operator')


ander_words = []
user_words = []
for seg, spk, sent, words in final_result:
    spk: str
    client_flag = True if spk is None or not spk.startswith(ander_spk) else False

    print('client:' if client_flag else 'operator:', sent)
    words_only = [x[0] for x in words]  # only worlds without timestamps

    if client_flag:
        user_words.extend(words_only)
    else:
        ander_words.extend(words_only)

print(ander_spk, 'is an operator')
print("Most common words:")
for spk in spk_query_fdist:
    print(spk, spk_query_fdist[spk].most_common(5))
print("Time: --- %s seconds ---" % (time.time() - start_time))
