import tkinter as tk
from tkinter import Label
from tkinter import scrolledtext
import os
import getpass

process_command = None
log_screen = None
cmd_screen = None
CMD_PROMPT = None
input_bar = None


def start_ui(cmd):
    global process_command
    global log_screen
    global CMD_PROMPT
    global input_bar
    global cmd_screen
    process_command = cmd
    ##################################################
    ### Screen Config variables ###
    LOG_SCREEN_Y = 20
    CMD_SCREEN_Y = 20

    cmd_path = "/".join(os.getcwd().split("/")[3:])
    if len(cmd_path) > 0:
        cmd_path = "/" + cmd_path
    CMD_PROMPT = "%s:~%s$ " % (getpass.getuser(), cmd_path)

    ##################################################
    ############## SETUP UI #############
    master = tk.Tk()
    master.title("3-Seas C&C")
    log_screen = scrolledtext.ScrolledText(master, height=LOG_SCREEN_Y, wrap=tk.WORD, bg="black", fg="white")
    cmd_screen = tk.Scrollbar(master, orient=tk.HORIZONTAL)
    cmd_screen = scrolledtext.ScrolledText(master, height=CMD_SCREEN_Y, wrap=tk.WORD, bg="black", fg="green")
    input_frame = tk.Frame(master, height=1, bg="black")
    input_bar = tk.Entry(input_frame, bg="black", fg="green")

    cmd_screen.insert("end", "Welcome to the 3 Seas Console!\n")
    cmd_screen.insert("end", CMD_PROMPT)

    input_cmd_label = Label(input_frame, text=CMD_PROMPT, bg="black", fg="green")
    input_cmd_label.configure(text=CMD_PROMPT)

    ########## SETUP UI POSITIONS ##########
    log_screen.pack(side=tk.TOP, fill=tk.X)
    # input_cmd_label.grid(row=1,column=1, sticky="w")
    # input_bar.grid(row=1,column=2,sticky="nsew")
    input_frame.pack(side=tk.BOTTOM, fill=tk.X)

    input_frame.grid_columnconfigure(1, weight=1)
    input_cmd_label.pack(side=tk.LEFT)
    input_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    cmd_screen.pack(side=tk.BOTTOM, fill=tk.X)
    cmd_screen.config(state='disabled')
    log_screen.config(state='disabled')
    log_screen.yview(tk.END)
    cmd_screen.yview(tk.END)
    input_bar.bind('<Return>', insert_raw_input)
    master.bind("<Return>", focus_input)
    tk.mainloop()


def insert_log(text):
    global log_screen
    log_screen.config(state='normal')
    log_screen.insert(tk.END, "%s\n" % (text))
    log_screen.config(state='disabled')
    log_screen.see("end")


def insert_cmd(text):
    global cmd_screen
    global CMD_PROMPT
    global input_bar
    cmd_screen.config(state='normal')
    cmd_screen.insert(tk.END, "%s\n%s" % (text, CMD_PROMPT))
    cmd_screen.config(state='disabled')
    cmd_screen.see("end")


def insert_raw_input(event):
    global input_bar
    global process_command
    input_line = input_bar.get()
    input_bar.delete(0, 'end')
    process_command(input_line)
    insert_cmd(input_line)


def focus_input(event):
    global input_bar
    input_bar.focus_set()
