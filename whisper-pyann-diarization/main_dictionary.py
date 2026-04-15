import tensorflow as tf
import tensorflow_text

module_url = "/home/tt/universal-sentence-encoder-multilingual-large_3"
embed = tf.saved_model.load(module_url)

# -------------- load dictinaries
from utils_dictionary import loads_dicts
dicts = loads_dicts('/home/u2/Downloads/dictionaries/vse')


# -------------- find by dictionary
from utils_dictionary import find_by_dictionary
for k,v in dicts.items():
    print("Dictionary:", k)
    find_by_dictionary(v, ander_words, embed)
