import stable_whisper as whisper

import datetime

import pandas as pd

import time

import numpy as np

from sklearn.cluster import AgglomerativeClustering

import torch

from pyannote.audio.pipelines.speaker_verification import PretrainedSpeakerEmbedding

from pyannote.audio import Audio

from pyannote.core import Segment

import wave

import contextlib

embedding_model = PretrainedSpeakerEmbedding(

    "speechbrain/spkrec-ecapa-voxceleb",

    device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))


def convert_time(secs):
    return datetime.timedelta(seconds=round(secs))


def speech_to_text(audio_file, lang, whisper_model, num_speakers):
    """

    1. Using Open AI's Whisper model to seperate audio into segments and generate transcripts.

    2. Generating speaker embeddings for each segments.

    3. Applying agglomerative clustering on the embeddings to identify the speaker for each segment.

    """

    model = whisper.load_model(whisper_model)

    time_start = time.time()

    if (audio_file == None):
        raise ValueError("Error no video input")

    print(audio_file)

    # os.system(f'ffmpeg -i "{mo3_file}" -ar 16000 -ac 1 -c:a pcm_s16le "{audio_file}"')

    try:

        # Get duration

        with contextlib.closing(wave.open(audio_file, 'r')) as f:

            frames = f.getnframes()

            rate = f.getframerate()

            duration = frames / float(rate)

        print(f"conversion to wav ready, duration of audio file: {duration}")

        # Transcribe audio

        print("starting whisper")

        options = dict(language=lang, beam_size=5, best_of=5)

        transcribe_options = dict(task="transcribe", **options)

        result = model.transcribe(audio_file, **transcribe_options)

        segments = result["segments"]

        print("done with whisper")

    except Exception as e:

        raise RuntimeError("Error transcribe")

    try:

        # Create embedding

        def segment_embedding(segment):

            audio = Audio()

            start = segment["start"]

            # Whisper overshoots the end timestamp in the last segment

            end = min(duration, segment["end"])

            clip = Segment(start, end)

            waveform, sample_rate = audio.crop(audio_file, clip)

            return embedding_model(waveform[None])

        embeddings = np.zeros(shape=(len(segments), 192))

        for i, segment in enumerate(segments):
            embeddings[i] = segment_embedding(segment)

        embeddings = np.nan_to_num(embeddings)

        print(f'Embedding shape: {embeddings.shape}')

        # Assign speaker label

        clustering = AgglomerativeClustering(num_speakers).fit(embeddings)

        labels = clustering.labels_

        for i in range(len(segments)):
            segments[i]["speaker"] = 'SPEAKER ' + str(labels[i] + 1)

        # Make output

        objects = {

            'Start': [],

            'End': [],

            'Speaker': [],

            'Text': []

        }

        text = ''

        for (i, segment) in enumerate(segments):

            if i == 0 or segments[i - 1]["speaker"] != segment["speaker"]:

                objects['Start'].append(str(convert_time(segment["start"])))

                objects['Speaker'].append(segment["speaker"])

                if i != 0:
                    objects['End'].append(str(convert_time(segments[i - 1]["end"])))

                    objects['Text'].append(text)

                    text = ''

            text += segment["text"] + ' '

        objects['End'].append(str(convert_time(segments[i - 1]["end"])))

        objects['Text'].append(text)

        time_end = time.time()

        time_diff = time_end - time_start

        # memory = psutil.virtual_memory()

        # gpu_utilization, gpu_memory = GPUInfo.gpu_usage()

        # gpu_utilization = gpu_utilization[0] if len(gpu_utilization) > 0 else 0

        # gpu_memory = gpu_memory[0] if len(gpu_memory) > 0 else 0

        # system_info = f"""

        # *Memory: {memory.total / (1024 * 1024 * 1024):.2f}GB, used: {memory.percent}%, available: {memory.available / (1024 * 1024 * 1024):.2f}GB.*

        # *Processing time: {time_diff:.5} seconds.*

        # *GPU Utilization: {gpu_utilization}%, GPU Memory: {gpu_memory}MiB.*

        # """

        return pd.DataFrame(objects), time_diff



    except Exception as e:

        raise RuntimeError("Error Running inference with local model", e)


res, td = speech_to_text("./wav/t.wav", "ru", "medium", 2)

print("total time ", td)

print(res)