from nltk.corpus import stopwords
from nltk.cluster.util import cosine_distance
import numpy as np
import nltk
from nltk.tokenize import sent_tokenize
import networkx as nx


def read_article_from_string(text):
    article = text.split(". ")
    sentences = []
    for sentence in article:
        sentences.append(sentence.replace("[^a-zA-Z]", " ").split(" "))
    if len(sentences) > 0:
        if len(sentences[-1]) == 0:  # removes the last empty item if it exists
            sentences.pop()
    return sentences


def sentence_similarity(sent1, sent2, stopwords=None):
    if stopwords is None:
        stopwords = []
    sent1 = [w.lower() for w in sent1 if w not in stopwords]
    sent2 = [w.lower() for w in sent2 if w not in stopwords]
    all_words = list(set(sent1 + sent2))
    vector1 = [0] * len(all_words)
    vector2 = [0] * len(all_words)
    for w in sent1:
        if w in stopwords:
            continue
        vector1[all_words.index(w)] += 1
    for w in sent2:
        if w in stopwords:
            continue
        vector2[all_words.index(w)] += 1
    return 1 - cosine_distance(vector1, vector2)


def build_similarity_matrix(sentences, stop_words):
    similarity_matrix = np.zeros((len(sentences), len(sentences)))
    for idx1 in range(len(sentences)):
        for idx2 in range(len(sentences)):
            if idx1 == idx2:
                continue
            similarity_matrix[idx1][idx2] = sentence_similarity(
                sentences[idx1], sentences[idx2], stop_words)
    return similarity_matrix


def generate_summary_from_text(text, top_n=5):
    nltk.download("stopwords")
    nltk.download("punkt")
    stop_words = stopwords.words('english')
    summarize_text = []
    sentences = read_article_from_string(text)
    sentence_similarity_matrix = build_similarity_matrix(sentences, stop_words)
    sentence_similarity_graph = nx.from_numpy_array(sentence_similarity_matrix)
    scores = nx.pagerank(sentence_similarity_graph)
    ranked_sentence = sorted(
        ((scores[i], s) for i, s in enumerate(sentences)), reverse=True)
    for i in range(top_n):
        summarize_text.append(" ".join(ranked_sentence[i][1]))

    return ". ".join(summarize_text)


# Example usage
long_text = """The Echo of Kindness

In a small town nestled between rolling hills and a sparkling river, there lived a high school student named Alex. Alex was known for being exceptionally bright but somewhat reserved, often lost in books and ideas.

One day, Alex's teacher announced a class project focused on community service. Each student was to choose an activity that would positively impact the community. While most students chose group activities, Alex decided to embark on a solo mission, uncertain about working in a team.

Alex chose to help Mrs. Jenkins, an elderly lady who lived alone at the edge of the town. Her garden, once her pride and joy, had become overgrown and neglected. Every afternoon, after school, Alex would go to Mrs. Jenkins' house to weed, plant, and water the garden. The task was daunting, and progress was slow, but Alex persevered.

As weeks passed, a transformation occurred. Not only did the garden begin to thrive, but Alex also began to open up. Mrs. Jenkins, with her wealth of stories and wisdom, became a friend and confidante. She shared tales of her youth, her travels, and the people she had met along the way. Her stories were filled with adventures, missteps, and, most importantly, acts of kindness she had experienced.

The day of the project presentation arrived. The class was astounded by the before and after pictures of Mrs. Jenkins' garden. But what truly captured their attention was Alex's presentation. Alex spoke not just of the physical labor but of the unexpected lessons learned from Mrs. Jenkins. The most profound lesson was about the power of kindness and how it echoes through time, impacting lives in ways one cannot foresee.

The story of Mrs. Jenkins' life, filled with small acts of kindness, had created ripples that reached far and wide, touching countless lives. Alex concluded by sharing a newfound belief: "In a world where you can be anything, be kind. Because kindness, like an echo, returns to you in ways you can't imagine."

The class was moved. Students who had never paid much attention to Alex now saw a different person — someone who had grown, learned, and shared a valuable lesson. From that day on, there was a noticeable change in the school's atmosphere. Acts of kindness, big and small, became more frequent. Students realized that their actions, like echoes, would reverberate beyond the halls of their school, into the community, and beyond.

"""
summary = generate_summary_from_text(long_text, 5)
print(summary)

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trader.settings')
django.setup()

from django.contrib.auth.models import User
from app.models import *

