# from huggingface_hub import notebook_login
# notebook_login()
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization@develop", use_auth_token=True)
pipeline