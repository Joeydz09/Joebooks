# -*- coding: utf-8 -*-
"""Joebooks Book Manager - local-first, backup-protected Tkinter app."""
import json, os, re, shutil, subprocess, sys, tempfile, webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = 'Ù…Ø¯ÙŠØ± Ù…ÙƒØªØ¨Ø© Ø§Ù„Ø£Ø­Ù„Ø§Ù… | Joebooks'
BASE = Path(__file__).resolve().parent
DATA = BASE / 'books.json'
COVERS = BASE / 'covers'
BACKUPS = BASE / 'book_adder_backups'
MAX_IMAGE = 20 * 1024 * 1024
REMOTE = 'origin'
BRANCH = 'main'


def git(*args, check=True):
    p = subprocess.run(['git', *args], cwd=str(BASE), text=True, encoding='utf-8', errors='replace', capture_output=True, shell=False)
    if check and p.returncode:
        raise RuntimeError((p.stderr or p.stdout or f'Git failed: {args}').strip())
    return p


def git_repo():
    p = git('rev-parse', '--show-toplevel', check=False)
    return p.returncode == 0 and Path(p.stdout.strip()).resolve() == BASE.resolve()


def normalize_url(raw):
    raw = raw.strip().rstrip('/')
    p = urlparse(raw)
    if p.scheme != 'https' or p.hostname not in ('t.me', 'www.t.me', 'telegram.me'):
        raise ValueError('Ø£Ø¯Ø®Ù„ Ø±Ø§Ø¨Ø· Ù…Ù†Ø´ÙˆØ± ØªÙŠÙ„ÙŠØ¬Ø±Ø§Ù… ÙŠØ¨Ø¯Ø£ Ø¨Ù€ https://t.me/')
    m = re.fullmatch(r'/([A-Za-z0-9_]+)/([0-9]+)', p.path)
    if not m or p.query or p.fragment:
        raise ValueError('Ø±Ø§Ø¨Ø· Ø§Ù„Ù…Ù†Ø´ÙˆØ± ØºÙŠØ± ØµØ§Ù„Ø­. Ù…Ø«Ø§Ù„: https://t.me/quotes_90/3217')
    return f'https://t.me/{m.group(1).lower()}/{int(m.group(2))}'


def read_books():
    if not DATA.is_file():
        raise ValueError(f'Ù„Ù… Ø£Ø¬Ø¯ books.json Ø¨Ø¬ÙˆØ§Ø± Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬:\n{DATA}\n\nØ¶Ø¹ Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ Ø¯Ø§Ø®Ù„ Ù†Ø³Ø®Ø© Ù…Ø´Ø±ÙˆØ¹ Ø§Ù„Ù…ÙˆÙ‚Ø¹.')
    try:
        books = json.loads(DATA.read_text(encoding='utf-8-sig'))
    except Exception as e:
        raise ValueError(f'ØªØ¹Ø°Ø±Øª Ù‚Ø±Ø§Ø¡Ø© books.json ÙƒÙ…Ù„Ù UTF-8 JSON ØµØ§Ù„Ø­:\n{e}')
    if not isinstance(books, list) or any(not isinstance(x, dict) for x in books):
        raise ValueError('ØµÙŠØºØ© books.json ØºÙŠØ± Ù…ØªÙˆÙ‚Ø¹Ø©: Ø§Ù„Ù…Ø·Ù„ÙˆØ¨ Ù‚Ø§Ø¦Ù…Ø© Ù…Ù† Ø³Ø¬Ù„Ø§Øª Ø§Ù„ÙƒØªØ¨.')
    return books


def backup_file(path):
    if not path.exists():
        return None
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    dest = BACKUPS / f'{path.name}.{stamp}.bak'
    shutil.copy2(path, dest)
    return dest


def image_extension(path):
    with open(path, 'rb') as f: h = f.read(16)
    if h.startswith(b'\xff\xd8\xff'): return '.jpg'
    if h.startswith(b'\x89PNG\r\n\x1a\n'): return '.png'
    if h[:4] == b'RIFF' and h[8:12] == b'WEBP': return '.webp'
    if h[:6] in (b'GIF87a', b'GIF89a'): return '.gif'
    raise ValueError('ØµÙŠØºØ© Ø§Ù„ØºÙ„Ø§Ù ØºÙŠØ± Ù…Ø¯Ø¹ÙˆÙ…Ø©. Ø§Ø³ØªØ®Ø¯Ù… JPG Ø£Ùˆ PNG Ø£Ùˆ WEBP Ø£Ùˆ GIF.')


def repo_status():
    p = git('status', '--porcelain', '--untracked-files=no')
    return [line for line in p.stdout.splitlines() if line.strip()]


class Manager:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry('900x780')
        root.minsize(760, 650)
        self.cover_path = tk.StringVar()
        self.status = tk.StringVar(value='Ø¬Ø§Ù‡Ø². Ø§Ø¨Ø¯Ø£ Ø¨ÙØ­Øµ Ø§ØªØµØ§Ù„ GitHub Ù‚Ø¨Ù„ Ø¥Ø¶Ø§ÙØ© ÙƒØªØ§Ø¨.')
        self.vars = {k: tk.StringVar() for k in ('title','author','category','pages','url')}
        self.build()
        self.refresh_count()

    def build(self):
        outer = ttk.Frame(self.root, padding=16); outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Ù…Ø¯ÙŠØ± Ù…ÙƒØªØ¨Ø© Ø§Ù„Ø£Ø­Ù„Ø§Ù…', font=('Segoe UI', 19, 'bold')).pack(anchor='e')
        ttk.Label(outer, text='Ø¥Ø¶Ø§ÙØ© ÙƒØªØ§Ø¨ØŒ Ø­ÙØ¸ Ù†Ø³Ø®Ø© Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©ØŒ Ø«Ù… Ù†Ø´Ø± Ø§Ù„Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø­Ø¯Ø¯Ø© ÙÙ‚Ø· Ø¹Ù„Ù‰ GitHub Pages', wraplength=820).pack(anchor='e', pady=(2,12))
        top = ttk.Frame(outer); top.pack(fill='x', pady=(0,10))
        self.count_label = ttk.Label(top, text=''); self.count_label.pack(side='right')
        ttk.Button(top, text='ÙØ­Øµ / Ù…Ø²Ø§Ù…Ù†Ø© Ø¢Ù…Ù†Ø© Ù…Ø¹ GitHub', command=self.sync).pack(side='left')
        form = ttk.Frame(outer); form.pack(fill='both', expand=True)
        fields = [('title','Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙƒØªØ§Ø¨ *'),('author','Ø§Ù„Ù…Ø¤Ù„Ù *'),('category','Ø§Ù„ØªØµÙ†ÙŠÙ'),('pages','Ø¹Ø¯Ø¯ Ø§Ù„ØµÙØ­Ø§Øª'),('url','Ø±Ø§Ø¨Ø· Ù…Ù†Ø´ÙˆØ± ØªÙŠÙ„ÙŠØ¬Ø±Ø§Ù… *')]
        for i,(key,label) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=1, sticky='e', padx=(8,0), pady=5)
            ttk.Entry(form, textvariable=self.vars[key], justify='right').grid(row=i, column=0, sticky='ew', pady=5)
        ttk.Label(form, text='Ø§Ù„Ù†Ø¨Ø°Ø©').grid(row=5, column=1, sticky='ne', padx=(8,0), pady=5)
        self.synopsis = tk.Text(form, height=7, wrap='word', font=('Segoe UI', 10))
        self.synopsis.grid(row=5, column=0, sticky='nsew', pady=5)
        ttk.Label(form, text='Ø§Ù„ØºÙ„Ø§Ù (Ø§Ø®ØªÙŠØ§Ø±ÙŠ)').grid(row=6, column=1, sticky='e', padx=(8,0), pady=5)
        coverrow = ttk.Frame(form); coverrow.grid(row=6, column=0, sticky='ew', pady=5)
        ttk.Entry(coverrow, textvariable=self.cover_path, state='readonly').pack(side='right', fill='x', expand=True)
        ttk.Button(coverrow, text='Ø§Ø®ØªÙŠØ§Ø± ØµÙˆØ±Ø©', command=self.pick_cover).pack(side='left', padx=(0,6))
        form.columnconfigure(0, weight=1); form.rowconfigure(5, weight=1)
        actions = ttk.Frame(outer); actions.pack(fill='x', pady=12)
        ttk.Button(actions, text='Ø­ÙØ¸ Ø§Ù„ÙƒØªØ§Ø¨ Ù…Ø­Ù„ÙŠÙ‹Ø§ Ù…Ø¹ Ù†Ø³Ø®Ø© Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©', command=self.save).pack(side='right', padx=4)
        ttk.Button(actions, text='Ù†Ø´Ø± Ø§Ù„ÙƒØªØ§Ø¨ Ø§Ù„Ù…Ø­Ø¯Ø¯ Ø¹Ù„Ù‰ GitHub', command=self.publish).pack(side='right', padx=4)
        ttk.Button(actions, text='ÙØªØ­ Ø§Ù„Ù…ÙˆÙ‚Ø¹', command=lambda: webbrowser.open('https://joeydz09.github.io/Joebooks/')).pack(side='left', padx=4)
        ttk.Button(actions, text='ÙØªØ­ Ù…Ø¬Ù„Ø¯ Ø§Ù„Ù†Ø³Ø® Ø§Ù„Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©', command=self.open_backups).pack(side='left', padx=4)
        ttk.Label(outer, textvariable=self.status, wraplength=840, justify='right').pack(fill='x', anchor='e')
        ttk.Label(outer, text='Ø­Ù…Ø§ÙŠØ©: Ù„Ø§ ÙŠØ­Ø°Ù Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ Ø§Ù„ÙƒØªØ¨Ø› ÙŠÙ†Ø´Ø¦ Ù†Ø³Ø®Ø© Ø§Ø­ØªÙŠØ§Ø·ÙŠØ© Ù‚Ø¨Ù„ ØªØ¹Ø¯ÙŠÙ„ books.jsonØŒ ÙˆÙŠØªÙˆÙ‚Ù Ø¥Ø°Ø§ ÙƒØ§Ù†Øª Ù†Ø³Ø®Ø© GitHub ØºÙŠØ± Ù…ØªØ²Ø§Ù…Ù†Ø© Ø£Ùˆ ÙƒØ§Ù†Øª Ù‡Ù†Ø§Ùƒ ØªØºÙŠÙŠØ±Ø§Øª Ù…Ø­Ù„ÙŠØ© ØºÙŠØ± Ù…Ø­ÙÙˆØ¸Ø©.', wraplength=840, foreground='#555').pack(anchor='e', pady=(8,0))

    def refresh_count(self):
        try: self.count_label.config(text=f'Ø¹Ø¯Ø¯ Ø§Ù„Ø³Ø¬Ù„Ø§Øª Ø§Ù„Ø­Ø§Ù„ÙŠ: {len(read_books())}')
        except Exception: self.count_label.config(text='ØªØ¹Ø°Ø± Ù‚Ø±Ø§Ø¡Ø© books.json')

    def pick_cover(self):
        p = filedialog.askopenfilename(title='Ø§Ø®ØªØ± ØºÙ„Ø§Ù Ø§Ù„ÙƒØªØ§Ø¨', filetypes=[('ØµÙˆØ±','*.jpg *.jpeg *.png *.webp *.gif'),('ÙƒÙ„ Ø§Ù„Ù…Ù„ÙØ§Øª','*.*')])
        if p: self.cover_path.set(p)

    def ensure_clean_synced(self):
        if not git_repo(): raise RuntimeError('Ù…Ø¬Ù„Ø¯ Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ Ù„ÙŠØ³ Ø¬Ø°Ø± Ù…Ø³ØªÙˆØ¯Ø¹ Git. Ø¶Ø¹ Ø§Ù„Ù…Ù„ÙØ§Øª Ø¯Ø§Ø®Ù„ Ù…Ø¬Ù„Ø¯ Joebooks_publish_work Ù†ÙØ³Ù‡.')
        status = repo_status()
        if status: raise RuntimeError('ØªÙˆØ¬Ø¯ ØªØºÙŠÙŠØ±Ø§Øª Ù…Ø­Ù„ÙŠØ© ÙÙŠ Ø§Ù„Ù…Ø³ØªÙˆØ¯Ø¹. Ø£ÙˆÙ‚ÙÙ†Ø§ Ø§Ù„Ø¹Ù…Ù„ÙŠØ© Ø­Ù…Ø§ÙŠØ©Ù‹ Ù„Ù…Ù„ÙØ§ØªÙƒ. Ø§ÙØ­Øµ Git Ù‚Ø¨Ù„ Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©:\n'+'\n'.join(status[:15]))
        git('fetch', REMOTE, BRANCH)
        head = git('rev-parse','HEAD').stdout.strip()
        remote = git('rev-parse',f'{REMOTE}/{BRANCH}').stdout.strip()
        if head == remote: return
        ancestor = git('merge-base','HEAD',f'{REMOTE}/{BRANCH}',check=False)
        if ancestor.returncode == 0 and ancestor.stdout.strip() == head:
            git('merge','--ff-only',f'{REMOTE}/{BRANCH}')
            return
        raise RuntimeError('Ù†Ø³Ø®ØªÙƒ Ø§Ù„Ù…Ø­Ù„ÙŠØ© Ù„ÙŠØ³Øª Ù…ØªØ²Ø§Ù…Ù†Ø© Ù…Ø¹ GitHub ÙˆÙ„Ø§ ÙŠÙ…ÙƒÙ† ØªØ­Ø¯ÙŠØ«Ù‡Ø§ Ø¨Ø£Ù…Ø§Ù† ØªÙ„Ù‚Ø§Ø¦ÙŠÙ‹Ø§. Ù„Ù… Ù†Ø­Ø°Ù Ø£Ùˆ Ù†Ø³ØªØ¨Ø¯Ù„ Ø£ÙŠ Ø´ÙŠØ¡. ÙŠÙ„Ø²Ù… ÙØ­Øµ Ø§Ù„Ø§Ø®ØªÙ„Ø§ÙØ§Øª ÙŠØ¯ÙˆÙŠÙ‹Ø§.')

    def sync(self):
        try:
            if not git_repo(): raise RuntimeError('Ø¶Ø¹ Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ Ø¯Ø§Ø®Ù„ Ù…Ø¬Ù„Ø¯ Ù…Ø³ØªÙˆØ¯Ø¹ Git Ø§Ù„ØµØ­ÙŠØ­ Ø£ÙˆÙ„Ù‹Ø§.')
            if repo_status(): raise RuntimeError('Ù‡Ù†Ø§Ùƒ ØªØºÙŠÙŠØ±Ø§Øª Ù…Ø­Ù„ÙŠØ© ØºÙŠØ± Ù…Ø­ÙÙˆØ¸Ø©. Ù„Ù† Ù†Ø²Ø§Ù…Ù† Ø­ØªÙ‰ Ù„Ø§ Ù†Ø®Ø§Ø·Ø± Ø¨Ù‡Ø§.')
            git('fetch', REMOTE, BRANCH)
            head = git('rev-parse','HEAD').stdout.strip(); remote = git('rev-parse',f'{REMOTE}/{BRANCH}').stdout.strip()
            if head == remote: msg='Ù†Ø³Ø®ØªÙƒ Ù…ØªØ²Ø§Ù…Ù†Ø© ØªÙ…Ø§Ù…Ù‹Ø§ Ù…Ø¹ GitHub.'
            else:
                base = git('merge-base','HEAD',f'{REMOTE}/{BRANCH}',check=False)
                if base.returncode == 0 and base.stdout.strip() == head:
                    git('merge','--ff-only',f'{REMOTE}/{BRANCH}')
                    msg='ØªÙ… ØªØ­Ø¯ÙŠØ« Ø§Ù„Ù†Ø³Ø®Ø© Ø§Ù„Ù…Ø­Ù„ÙŠØ© Ø¨ØªÙ‚Ø¯ÙŠÙ… Ø³Ø±ÙŠØ¹ Ø¢Ù…Ù† (fast-forward)ØŒ Ø¯ÙˆÙ† Ø­Ø°Ù ØªØºÙŠÙŠØ±Ø§Øª.'
                else: raise RuntimeError('Ù‡Ù†Ø§Ùƒ Ø§Ø®ØªÙ„Ø§Ù Ù…ØªØ´Ø¹Ø¨ Ø¨ÙŠÙ† Ø§Ù„Ù…Ø­Ù„ÙŠ ÙˆGitHub. Ù„Ù… Ù†ØºÙŠÙ‘Ø± Ø§Ù„Ù…Ù„ÙØ§ØªØ› ÙŠÙ„Ø²Ù… Ø­Ù„Ù‘Ù‡ ÙŠØ¯ÙˆÙŠÙ‹Ø§.')
            self.status.set(msg); self.refresh_count(); messagebox.showinfo('ÙØ­Øµ Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø©',msg)
        except Exception as e: messagebox.showerror('ØªØ¹Ø°Ø± Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø©',str(e)); self.status.set('Ù„Ù… ØªÙƒØªÙ…Ù„ Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø©Ø› Ù„Ù… ÙŠØªÙ… Ù†Ø´Ø± Ø´ÙŠØ¡.')

    def build_record(self, books):
        v={k:x.get().strip() for k,x in self.vars.items()}
        v['synopsis']=self.synopsis.get('1.0','end').strip()
        if not v['title'] or not v['author']: raise ValueError('Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙƒØªØ§Ø¨ ÙˆØ§Ø³Ù… Ø§Ù„Ù…Ø¤Ù„Ù Ù…Ø·Ù„ÙˆØ¨Ø§Ù†.')
        url=normalize_url(v['url'])
        if v['pages'] and (not v['pages'].isdigit() or int(v['pages'])<1): raise ValueError('Ø¹Ø¯Ø¯ Ø§Ù„ØµÙØ­Ø§Øª ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø¹Ø¯Ø¯Ù‹Ø§ ØµØ­ÙŠØ­Ù‹Ø§ Ù…ÙˆØ¬Ø¨Ù‹Ø§ Ø£Ùˆ ÙŠØªØ±Ùƒ ÙØ§Ø±ØºÙ‹Ø§.')
        for b in books:
            if str(b.get('url','')).rstrip('/').lower()==url.lower(): raise ValueError(f'Ø±Ø§Ø¨Ø· Ù‡Ø°Ø§ Ø§Ù„Ù…Ù†Ø´ÙˆØ± Ù…ÙˆØ¬ÙˆØ¯ Ù…Ø³Ø¨Ù‚Ù‹Ø§ (ID: {b.get("id","ØŸ")}).')
        ids=[]
        for b in books:
            try: ids.append(int(b['id']))
            except Exception: raise ValueError('ÙŠÙˆØ¬Ø¯ Ø³Ø¬Ù„ Ø¨Ù…Ø¹Ø±Ù‘Ù ØºÙŠØ± ØµØ§Ù„Ø­. Ø£ÙˆÙ‚ÙÙ†Ø§ Ø§Ù„Ø¥Ø¶Ø§ÙØ© Ø­Ù…Ø§ÙŠØ©Ù‹ Ù„Ù„Ø¨ÙŠØ§Ù†Ø§Øª.')
        record={'id':max(ids,default=0)+1,'title':v['title'],'author':v['author'],'url':url,'category':v['category'] or 'ØºÙŠØ± Ù…ØµÙ†Ù','source':'channel'}
        if v['pages']: record['pages']=int(v['pages'])
        if v['synopsis']: record['synopsis']=v['synopsis']
        return record

    def save(self):
        try:
            # Sync before writing so we never strand a new local edit on a stale branch.
            self.ensure_clean_synced()
            books=read_books(); record=self.build_record(books)
            image=self.cover_path.get().strip(); dest=None
            if image:
                src=Path(image)
                if not src.is_file(): raise ValueError('Ù…Ù„Ù Ø§Ù„ØºÙ„Ø§Ù ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯.')
                if src.stat().st_size>MAX_IMAGE: raise ValueError('Ø­Ø¬Ù… Ø§Ù„ØºÙ„Ø§Ù Ø£ÙƒØ¨Ø± Ù…Ù† 20 Ù…ÙŠØºØ§Ø¨Ø§ÙŠØª.')
                ext=image_extension(src); COVERS.mkdir(exist_ok=True)
                dest=COVERS/f'book_{record["id"]}{ext}'
                if dest.exists(): raise ValueError(f'Ù…Ù„Ù Ø§Ù„ØºÙ„Ø§Ù Ù…ÙˆØ¬ÙˆØ¯ Ù…Ø³Ø¨Ù‚Ù‹Ø§: {dest.name}. Ù„Ù… Ù†Ø³ØªØ¨Ø¯Ù„Ù‡.')
                record['cover'] = dest.relative_to(BASE).as_posix()
            books.insert(0, record)
            backup=backup_file(DATA)
            cover_created=False
            try:
                if dest:
                    shutil.copy2(image,dest); cover_created=True
                tmp=DATA.with_name('books.json.tmp')
                tmp.write_text(json.dumps(books,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                json.loads(tmp.read_text(encoding='utf-8'))
                os.replace(tmp,DATA)
            except Exception:
                if cover_created and dest and dest.exists(): dest.unlink()
                raise
            self.pending_paths=['books.json']+([dest.relative_to(BASE).as_posix()] if dest else [])
            self.pending_id=record['id']
            self.status.set(f'ØªÙ… Ø­ÙØ¸ Ø§Ù„ÙƒØªØ§Ø¨ ID {record["id"]} Ù…Ø­Ù„ÙŠÙ‹Ø§. Ø§Ù„Ù†Ø³Ø®Ø© Ø§Ù„Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©: {backup.name if backup else "ØºÙŠØ± Ù…Ø·Ù„ÙˆØ¨Ø©"}. Ù„Ù… ÙŠÙÙ†Ø´Ø± Ø¨Ø¹Ø¯.')
            self.refresh_count(); messagebox.showinfo('ØªÙ… Ø§Ù„Ø­ÙØ¸ Ù…Ø­Ù„ÙŠÙ‹Ø§',f'ØªÙ…Øª Ø¥Ø¶Ø§ÙØ© Ø§Ù„ÙƒØªØ§Ø¨ ID {record["id"]}.\nØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ù†Ø³Ø®Ø© Ø§Ø­ØªÙŠØ§Ø·ÙŠØ© Ù‚Ø¨Ù„ ØªØ¹Ø¯ÙŠÙ„ books.json.\n\nØ§Ø¶ØºØ· Â«Ù†Ø´Ø± Ø§Ù„ÙƒØªØ§Ø¨ Ø§Ù„Ù…Ø­Ø¯Ø¯ Ø¹Ù„Ù‰ GitHubÂ» Ø¨Ø¹Ø¯ Ø§Ù„ØªØ£ÙƒØ¯ Ù…Ù† Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª.')
        except Exception as e: messagebox.showerror('ØªØ¹Ø°Ø± Ø§Ù„Ø­ÙØ¸',str(e)); self.status.set('Ù„Ù… ÙŠØªÙ… Ø¥ÙƒÙ…Ø§Ù„ Ø§Ù„Ø­ÙØ¸.')

    def publish(self):
        if not getattr(self,'pending_paths',None):
            messagebox.showwarning('Ù„Ø§ ÙŠÙˆØ¬Ø¯ ÙƒØªØ§Ø¨ Ù…Ø¹Ù„Ù‘Ù‚','Ø§Ø­ÙØ¸ ÙƒØªØ§Ø¨Ù‹Ø§ Ø¬Ø¯ÙŠØ¯Ù‹Ø§ Ø£ÙˆÙ„Ù‹Ø§. Ù„Ø§ ÙŠÙ…ÙƒÙ† Ù†Ø´Ø± ØªØºÙŠÙŠØ±Ø§Øª ØºÙŠØ± Ù…Ø­Ø¯Ø¯Ø© Ù…Ù† Ù‡Ø°Ù‡ Ø§Ù„ÙˆØ§Ø¬Ù‡Ø©.'); return
        try:
            if not git_repo(): raise RuntimeError('Ù‡Ø°Ø§ Ø§Ù„Ù…Ø¬Ù„Ø¯ Ù„ÙŠØ³ Ù…Ø³ØªÙˆØ¯Ø¹ Git Ø§Ù„ØµØ­ÙŠØ­.')
            # Ensure only the files belonging to this pending book are modified.
            changed=repo_status()
            allowed=set(self.pending_paths)
            unexpected=[]
            for line in changed:
                path=line[3:].strip().replace('\\','/')
                if path not in allowed: unexpected.append(line)
            if unexpected: raise RuntimeError('Ø¸Ù‡Ø±Øª ØªØºÙŠÙŠØ±Ø§Øª Ø£Ø®Ø±Ù‰ ØºÙŠØ± Ù…Ø±ØªØ¨Ø·Ø© Ø¨Ø§Ù„ÙƒØªØ§Ø¨. Ù„Ù† Ù†Ù†Ø´Ø±Ù‡Ø§:\n'+'\n'.join(unexpected[:12]))
            git('fetch',REMOTE,BRANCH)
            head=git('rev-parse','HEAD').stdout.strip(); remote=git('rev-parse',f'{REMOTE}/{BRANCH}').stdout.strip()
            if head!=remote: raise RuntimeError('GitHub ØªØºÙŠÙ‘Ø± Ù…Ù†Ø° Ø¢Ø®Ø± Ù…Ø²Ø§Ù…Ù†Ø©. Ù„Ù… Ù†Ù†Ø´Ø± Ø´ÙŠØ¦Ù‹Ø§. Ø§Ø³ØªØ®Ø¯Ù… Â«ÙØ­Øµ / Ù…Ø²Ø§Ù…Ù†Ø© Ø¢Ù…Ù†Ø©Â»ØŒ Ø«Ù… Ø£Ø¹Ø¯ Ù…Ø±Ø§Ø¬Ø¹Ø© Ø§Ù„ÙƒØªØ§Ø¨.')
            if not messagebox.askyesno('ØªØ£ÙƒÙŠØ¯ Ø§Ù„Ù†Ø´Ø±',f'Ù‡Ù„ ØªØ±ÙŠØ¯ Ù†Ø´Ø± Ø§Ù„ÙƒØªØ§Ø¨ ID {getattr(self,"pending_id","ØŸ")} ÙˆØ§Ù„Ù…Ù„ÙØ§Øª Ø§Ù„ØªØ§Ø¨Ø¹Ø© Ù„Ù‡ ÙÙ‚Ø·ØŸ\n\nÙ„Ù† Ù†Ø¶ÙŠÙ Ø£ÙŠ Ù…Ù„Ù Ø¢Ø®Ø± Ø¥Ù„Ù‰ Ø§Ù„Ø§Ù„ØªØ²Ø§Ù….'):
                return
            git('add','--',*self.pending_paths)
            git('commit','--only','-m',f'Add book {getattr(self,"pending_id","new")}', '--',*self.pending_paths)
            git('push',REMOTE,BRANCH)
            self.pending_paths=[]
            self.status.set('ØªÙ… Ø§Ù„Ù†Ø´Ø± Ø¥Ù„Ù‰ GitHub Ø¨Ù†Ø¬Ø§Ø­. Ù‚Ø¯ ÙŠØ³ØªØºØ±Ù‚ ØªØ­Ø¯ÙŠØ« Ø§Ù„Ù…ÙˆÙ‚Ø¹ Ø¨Ø¶Ø¹ Ø¯Ù‚Ø§Ø¦Ù‚.')
            messagebox.showinfo('ØªÙ… Ø§Ù„Ù†Ø´Ø±','ØªÙ… Ø±ÙØ¹ Ø§Ù„ÙƒØªØ§Ø¨ ÙˆØ§Ù„Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø­Ø¯Ø¯Ø© ÙÙ‚Ø· Ø¥Ù„Ù‰ GitHub. ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„Ù…ÙˆÙ‚Ø¹ Ø¨Ø¹Ø¯ Ø¯Ù‚Ø§Ø¦Ù‚.'); webbrowser.open('https://joeydz09.github.io/Joebooks/')
        except Exception as e: messagebox.showerror('ØªØ¹Ø°Ø± Ø§Ù„Ù†Ø´Ø±',str(e)); self.status.set('Ù„Ù… ÙŠÙƒØªÙ…Ù„ Ø§Ù„Ù†Ø´Ø±. Ø§Ø­ØªÙØ¸Ù†Ø§ Ø¨Ø§Ù„Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø­Ù„ÙŠØ© ÙˆØ§Ù„Ù†Ø³Ø® Ø§Ù„Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©.')

    def open_backups(self):
        BACKUPS.mkdir(parents=True,exist_ok=True)
        try: os.startfile(str(BACKUPS))
        except Exception: messagebox.showinfo('Ù…Ø¬Ù„Ø¯ Ø§Ù„Ù†Ø³Ø® Ø§Ù„Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©',str(BACKUPS))


def main():
    root=tk.Tk();
    try: ttk.Style().theme_use('vista')
    except tk.TclError: pass
    Manager(root); root.mainloop()

if __name__=='__main__': main()

