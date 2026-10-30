# -*- coding: utf-8 -*-
"""Joebooks Book Manager - local-first, backup-protected Tkinter app."""
import json, os, re, shutil, subprocess, sys, tempfile, webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = 'مدير مكتبة الأحلام | Joebooks'
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
        raise ValueError('أدخل رابط منشور تيليجرام يبدأ بـ https://t.me/')
    m = re.fullmatch(r'/([A-Za-z0-9_]+)/([0-9]+)', p.path)
    if not m or p.query or p.fragment:
        raise ValueError('رابط المنشور غير صالح. مثال: https://t.me/quotes_90/3217')
    return f'https://t.me/{m.group(1).lower()}/{int(m.group(2))}'


def read_books():
    if not DATA.is_file():
        raise ValueError(f'لم أجد books.json بجوار البرنامج:\n{DATA}\n\nضع البرنامج داخل نسخة مشروع الموقع.')
    try:
        books = json.loads(DATA.read_text(encoding='utf-8-sig'))
    except Exception as e:
        raise ValueError(f'تعذرت قراءة books.json كملف UTF-8 JSON صالح:\n{e}')
    if not isinstance(books, list) or any(not isinstance(x, dict) for x in books):
        raise ValueError('صيغة books.json غير متوقعة: المطلوب قائمة من سجلات الكتب.')
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
    raise ValueError('صيغة الغلاف غير مدعومة. استخدم JPG أو PNG أو WEBP أو GIF.')


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
        self.status = tk.StringVar(value='جاهز. ابدأ بفحص اتصال GitHub قبل إضافة كتاب.')
        self.vars = {k: tk.StringVar() for k in ('title','author','category','pages','url')}
        self.build()
        self.refresh_count()

    def build(self):
        outer = ttk.Frame(self.root, padding=16); outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='مدير مكتبة الأحلام', font=('Segoe UI', 19, 'bold')).pack(anchor='e')
        ttk.Label(outer, text='إضافة كتاب، حفظ نسخة احتياطية، ثم نشر الملفات المحددة فقط على GitHub Pages', wraplength=820).pack(anchor='e', pady=(2,12))
        top = ttk.Frame(outer); top.pack(fill='x', pady=(0,10))
        self.count_label = ttk.Label(top, text=''); self.count_label.pack(side='right')
        ttk.Button(top, text='فحص / مزامنة آمنة مع GitHub', command=self.sync).pack(side='left')
        form = ttk.Frame(outer); form.pack(fill='both', expand=True)
        fields = [('title','عنوان الكتاب *'),('author','المؤلف *'),('category','التصنيف'),('pages','عدد الصفحات'),('url','رابط منشور تيليجرام *')]
        for i,(key,label) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=1, sticky='e', padx=(8,0), pady=5)
            ttk.Entry(form, textvariable=self.vars[key], justify='right').grid(row=i, column=0, sticky='ew', pady=5)
        ttk.Label(form, text='النبذة').grid(row=5, column=1, sticky='ne', padx=(8,0), pady=5)
        self.synopsis = tk.Text(form, height=7, wrap='word', font=('Segoe UI', 10))
        self.synopsis.grid(row=5, column=0, sticky='nsew', pady=5)
        ttk.Label(form, text='الغلاف (اختياري)').grid(row=6, column=1, sticky='e', padx=(8,0), pady=5)
        coverrow = ttk.Frame(form); coverrow.grid(row=6, column=0, sticky='ew', pady=5)
        ttk.Entry(coverrow, textvariable=self.cover_path, state='readonly').pack(side='right', fill='x', expand=True)
        ttk.Button(coverrow, text='اختيار صورة', command=self.pick_cover).pack(side='left', padx=(0,6))
        form.columnconfigure(0, weight=1); form.rowconfigure(5, weight=1)
        actions = ttk.Frame(outer); actions.pack(fill='x', pady=12)
        ttk.Button(actions, text='حفظ الكتاب محليًا مع نسخة احتياطية', command=self.save).pack(side='right', padx=4)
        ttk.Button(actions, text='نشر الكتاب المحدد على GitHub', command=self.publish).pack(side='right', padx=4)
        ttk.Button(actions, text='فتح الموقع', command=lambda: webbrowser.open('https://joeydz09.github.io/Joebooks/')).pack(side='left', padx=4)
        ttk.Button(actions, text='فتح مجلد النسخ الاحتياطية', command=self.open_backups).pack(side='left', padx=4)
        ttk.Label(outer, textvariable=self.status, wraplength=840, justify='right').pack(fill='x', anchor='e')
        ttk.Label(outer, text='حماية: لا يحذف البرنامج الكتب؛ ينشئ نسخة احتياطية قبل تعديل books.json، ويتوقف إذا كانت نسخة GitHub غير متزامنة أو كانت هناك تغييرات محلية غير محفوظة.', wraplength=840, foreground='#555').pack(anchor='e', pady=(8,0))

    def refresh_count(self):
        try: self.count_label.config(text=f'عدد السجلات الحالي: {len(read_books())}')
        except Exception: self.count_label.config(text='تعذر قراءة books.json')

    def pick_cover(self):
        p = filedialog.askopenfilename(title='اختر غلاف الكتاب', filetypes=[('صور','*.jpg *.jpeg *.png *.webp *.gif'),('كل الملفات','*.*')])
        if p: self.cover_path.set(p)

    def ensure_clean_synced(self):
        if not git_repo(): raise RuntimeError('مجلد البرنامج ليس جذر مستودع Git. ضع الملفات داخل مجلد Joebooks_publish_work نفسه.')
        status = repo_status()
        if status: raise RuntimeError('توجد تغييرات محلية في المستودع. أوقفنا العملية حمايةً لملفاتك. افحص Git قبل المتابعة:\n'+'\n'.join(status[:15]))
        git('fetch', REMOTE, BRANCH)
        head = git('rev-parse','HEAD').stdout.strip()
        remote = git('rev-parse',f'{REMOTE}/{BRANCH}').stdout.strip()
        if head == remote: return
        ancestor = git('merge-base','HEAD',f'{REMOTE}/{BRANCH}',check=False)
        if ancestor.returncode == 0 and ancestor.stdout.strip() == head:
            git('merge','--ff-only',f'{REMOTE}/{BRANCH}')
            return
        raise RuntimeError('نسختك المحلية ليست متزامنة مع GitHub ولا يمكن تحديثها بأمان تلقائيًا. لم نحذف أو نستبدل أي شيء. يلزم فحص الاختلافات يدويًا.')

    def sync(self):
        try:
            if not git_repo(): raise RuntimeError('ضع البرنامج داخل مجلد مستودع Git الصحيح أولًا.')
            if repo_status(): raise RuntimeError('هناك تغييرات محلية غير محفوظة. لن نزامن حتى لا نخاطر بها.')
            git('fetch', REMOTE, BRANCH)
            head = git('rev-parse','HEAD').stdout.strip(); remote = git('rev-parse',f'{REMOTE}/{BRANCH}').stdout.strip()
            if head == remote: msg='نسختك متزامنة تمامًا مع GitHub.'
            else:
                base = git('merge-base','HEAD',f'{REMOTE}/{BRANCH}',check=False)
                if base.returncode == 0 and base.stdout.strip() == head:
                    git('merge','--ff-only',f'{REMOTE}/{BRANCH}')
                    msg='تم تحديث النسخة المحلية بتقديم سريع آمن (fast-forward)، دون حذف تغييرات.'
                else: raise RuntimeError('هناك اختلاف متشعب بين المحلي وGitHub. لم نغيّر الملفات؛ يلزم حلّه يدويًا.')
            self.status.set(msg); self.refresh_count(); messagebox.showinfo('فحص المزامنة',msg)
        except Exception as e: messagebox.showerror('تعذر المزامنة',str(e)); self.status.set('لم تكتمل المزامنة؛ لم يتم نشر شيء.')

    def build_record(self, books):
        v={k:x.get().strip() for k,x in self.vars.items()}
        v['synopsis']=self.synopsis.get('1.0','end').strip()
        if not v['title'] or not v['author']: raise ValueError('عنوان الكتاب واسم المؤلف مطلوبان.')
        url=normalize_url(v['url'])
        if v['pages'] and (not v['pages'].isdigit() or int(v['pages'])<1): raise ValueError('عدد الصفحات يجب أن يكون عددًا صحيحًا موجبًا أو يترك فارغًا.')
        for b in books:
            if str(b.get('url','')).rstrip('/').lower()==url.lower(): raise ValueError(f'رابط هذا المنشور موجود مسبقًا (ID: {b.get("id","؟")}).')
        ids=[]
        for b in books:
            try: ids.append(int(b['id']))
            except Exception: raise ValueError('يوجد سجل بمعرّف غير صالح. أوقفنا الإضافة حمايةً للبيانات.')
        record={'id':max(ids,default=0)+1,'title':v['title'],'author':v['author'],'url':url,'category':v['category'] or 'غير مصنف','source':'channel'}
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
                if not src.is_file(): raise ValueError('ملف الغلاف غير موجود.')
                if src.stat().st_size>MAX_IMAGE: raise ValueError('حجم الغلاف أكبر من 20 ميغابايت.')
                ext=image_extension(src); COVERS.mkdir(exist_ok=True)
                dest=COVERS/f'book_{record["id"]}{ext}'
                if dest.exists(): raise ValueError(f'ملف الغلاف موجود مسبقًا: {dest.name}. لم نستبدله.')
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
            self.status.set(f'تم حفظ الكتاب ID {record["id"]} محليًا. النسخة الاحتياطية: {backup.name if backup else "غير مطلوبة"}. لم يُنشر بعد.')
            self.refresh_count(); messagebox.showinfo('تم الحفظ محليًا',f'تمت إضافة الكتاب ID {record["id"]}.\nتم إنشاء نسخة احتياطية قبل تعديل books.json.\n\nاضغط «نشر الكتاب المحدد على GitHub» بعد التأكد من البيانات.')
        except Exception as e: messagebox.showerror('تعذر الحفظ',str(e)); self.status.set('لم يتم إكمال الحفظ.')

    def publish(self):
        if not getattr(self,'pending_paths',None):
            messagebox.showwarning('لا يوجد كتاب معلّق','احفظ كتابًا جديدًا أولًا. لا يمكن نشر تغييرات غير محددة من هذه الواجهة.'); return
        try:
            if not git_repo(): raise RuntimeError('هذا المجلد ليس مستودع Git الصحيح.')
            # Ensure only the files belonging to this pending book are modified.
            changed=repo_status()
            allowed=set(self.pending_paths)
            unexpected=[]
            for line in changed:
                path=line[3:].strip().replace('\\','/')
                if path not in allowed: unexpected.append(line)
            if unexpected: raise RuntimeError('ظهرت تغييرات أخرى غير مرتبطة بالكتاب. لن ننشرها:\n'+'\n'.join(unexpected[:12]))
            git('fetch',REMOTE,BRANCH)
            head=git('rev-parse','HEAD').stdout.strip(); remote=git('rev-parse',f'{REMOTE}/{BRANCH}').stdout.strip()
            if head!=remote: raise RuntimeError('GitHub تغيّر منذ آخر مزامنة. لم ننشر شيئًا. استخدم «فحص / مزامنة آمنة»، ثم أعد مراجعة الكتاب.')
            if not messagebox.askyesno('تأكيد النشر',f'هل تريد نشر الكتاب ID {getattr(self,"pending_id","؟")} والملفات التابعة له فقط؟\n\nلن نضيف أي ملف آخر إلى الالتزام.'):
                return
            git('add','--',*self.pending_paths)
            git('commit','--only','-m',f'Add book {getattr(self,"pending_id","new")}', '--',*self.pending_paths)
            git('push',REMOTE,BRANCH)
            self.pending_paths=[]
            self.status.set('تم النشر إلى GitHub بنجاح. قد يستغرق تحديث الموقع بضع دقائق.')
            messagebox.showinfo('تم النشر','تم رفع الكتاب والملفات المحددة فقط إلى GitHub. تحقق من الموقع بعد دقائق.'); webbrowser.open('https://joeydz09.github.io/Joebooks/')
        except Exception as e: messagebox.showerror('تعذر النشر',str(e)); self.status.set('لم يكتمل النشر. احتفظنا بالملفات المحلية والنسخ الاحتياطية.')

    def open_backups(self):
        BACKUPS.mkdir(parents=True,exist_ok=True)
        try: os.startfile(str(BACKUPS))
        except Exception: messagebox.showinfo('مجلد النسخ الاحتياطية',str(BACKUPS))


def main():
    root=tk.Tk();
    try: ttk.Style().theme_use('vista')
    except tk.TclError: pass
    Manager(root); root.mainloop()

if __name__=='__main__': main()
