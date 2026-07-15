#!/usr/bin/env python3
import os, json, tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2

DIR = os.path.expanduser('~/Desktop/paintings')
ARTWORKS_DIR = os.path.join(DIR, 'artworks')
AVATARS_DIR = os.path.join(DIR, 'avatars')
JSON_PATH = os.path.join(AVATARS_DIR, 'avatars.json')
PAINTINGS_JSON = os.path.join(DIR, 'monet_paintings.json')
IMG_MAX = 900
HANDLE_SIZE = 6
MIN_BBOX = 10
