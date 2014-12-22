from tkinter import * # ui library
from tkinter import ttk # themed ui components that match the OS
from tkinter import font, messagebox # simple, standard modal dialogs
from tkinter import filedialog # open/save as dialog creator
from tkinter import simpledialog # Premade windows for asking for strings/ints/etc
from functools import partial as func_partial
import random
import itertools
import math

import tkinter_png as png # png library for TKinter

from property_parser import Property
from config import ConfigFile
from paletteLoader import Palette
import packageLoader as package
import contextWin
import loadScreen as loader
import gameMan
from gameMan import translate as P2_trans
from selectorWin import selWin
from selectorWin import Item as selWinItem
import sound as snd

win=Tk()
win.withdraw() # hide the main window while everything is loading, so you don't see the bits appearing
gameMan.root=win

gameMan.load_trans_data()

png.img_error=png.loadPng('BEE2/error') # If image is not readable, use this instead
           
item_list = {}

win.iconbitmap('BEE2.ico')# set the window icon

windows={}
frames={} #Holds frames that we need to deal with later
UI={} # Other ui elements we need to access
menus={} # The menu items for the main window
pal_picked=[] # array of the picker icons
pal_items=[] # array of the "all items" icons
pal_picked_fake = [] # Labels used for the empty palette positions
drag_item=-1 # the item currently being moved
drag_orig_pos=-1
drag_onPal=False # are we dragging a palette item?
drag_passedPal=False # has the cursor passed over the palette
FILTER_CATS=('author','package','tags')
FilterBoxes={} # the various checkboxes for the filters
FilterBoxes_all={}
FilterVars={} # The variables for the checkboxes
FilterVars_all={}
filter_expanded = False
Settings=None
ItemsBG="#CDD0CE" # Colour of the main background to match the menu image
selectedPalette = 0
selectedGame=0
PalEntry_TempText="New Palette>"
PalEntry = StringVar(value=PalEntry_TempText)
selectedPalette_radio = IntVar(value=0) # fake value the menu radio buttons set
shouldSnap=True # Should we update the relative positions of windows?
muted = IntVar(value=0) # Is the sound fx muted?

# UI vars, TODO: most should be generated on startup
paletteReadOnly=('Empty','Portal 2') # Don't let the user edit these, they're special
palettes=[]

skyboxes = {}
voices = {}
styles = {}
musics = {}
goos = {}
stylevar_list = []

selected_style = "BEE2_CLEAN"

authorText = ('BenVlodgi & Rantis','HMW','Carl Kenner', 'Felix Griffin', 'Bisqwit', 'TeamSpen210')
packageText = ('BEEMOD', 'BEE2', 'HMW', 'Stylemod', 'FGEmod')
tagText = ('Test Elements', 'Panels', 'Geometry', 'Logic', 'Custom')

styleOptions = [('MultiverseCave','Multiverse Cave', 1),
                ('FixPortalBump','Prevent Portal Bump  (glass)', 0),
                ('FixFizzlerBump','Prevent Portal Bump  (fizzler)', 0), # these four should be hardcoded (part of Portal 2 basically), other settings should be extracted from style file and put into cats
                ('NoMidVoices','Suppress Mid-Chamber Dialogue', 0)
               ]

styleCheck_enabled={}
styleCheck={}
styleCheck_disabled={}
styleOptVars={}

item_opts = ConfigFile('item_configs.cfg')
# A config file which remembers changed property options, chosen versions, etc

class Item():
    '''Represents an item that can appear on the list.'''
    def __init__(self, item):
        self.ver = int(item_opts.get_val(item.id, 'sel_version', '0'))
        self.item = item
        self.def_data = self.item.def_data
        # These pieces of data are constant, only from the first style.
        self.num_sub = len(list(Property.find_all(self.def_data['editor'], "Item", "Editor", "Subtype")))
        self.authors = self.def_data['auth']
        self.tags = self.def_data['tags']
        
        self.load_data()
        self.id = item.id
        self.pak_id = item.pak_id
        self.pak_name = item.pak_name
        self.set_properties(self.get_properties())
        
    def load_data(self):
        '''Load data from the item.'''
        self.data=self.item.versions[self.ver]['styles'][selected_style]
        self.names = [prop.value for prop in Property.find_all(self.data['editor'], "Item", "Editor", "Subtype", "Name")]
        self.url = self.data['url']
        
    def get_icon(self, subKey, allow_single=False, single_num=1):
        icons = self.data['icons']
        if (allow_single and 'all' in icons and 
            sum(1 for item in pal_picked if item.id==self.id) <= single_num):
            # If only 1 copy of this item is on the palette, use the special icon
            return png.loadIcon(icons['all'])
        else:
            return png.loadIcon(icons[str(subKey)])
            
    def properties(self):
        '''Iterate through all properties for this item.'''
        for part in Property.find_all(self.data['editor'], "Item", "Properties"):
            for prop in part:
                yield prop.name.casefold()
    
    def get_properties(self):
        '''Return a dictionary of properties and the current value associated with them.'''
        result = {}
        for part in Property.find_all(self.data['editor'], "Item", "Properties"):
            for prop in part:
                name = prop.name.casefold()
                if name not in result:
                    result[name] = item_opts.get_val(self.id, 'PROP_' + name, prop["DefaultValue", None])
        return result
        
    def set_properties(self, props):
        '''Apply the properties to the item.'''
        editor_tree = Property.find_all(self.data['editor'], "Item", "Properties")
        for prop, value in props.items():
            for def_prop in Property.find_all(editor_tree, prop, 'DefaultValue'):
                def_prop.value = str(value)
            item_opts[self.id]['PROP_' + prop] = str(value)
            
    def export(self):
        '''Generate the editoritems and vbsp_config values that represent this item.'''
        print(self.id)
        self.load_data()
        
        palette_items = {}
        for item in pal_picked:
            if item.id == self.id:
                palette_items[item.subKey] = item
        
        new_editor = [prop.copy() for prop in self.data['editor']]
        for index, editor_section in enumerate(Property.find_all(new_editor, "Item", "Editor", "Subtype")):
            for editor_sec_index, pal_section in enumerate(editor_section.value):
                if pal_section.name.casefold() == "palette":
                    if index in palette_items:
                        if len(palette_items) == 1:
                            # Switch to the 'Grouped' icon
                            if self.data['all_name'] is not None:
                                pal_section['Tooltip'] = self.data['all_name']
                            if self.data['all_icon'] is not None:
                                pal_section['Image'] = self.data['all_icon']
                        
                        pal_section['Position'] = (str(palette_items[index].pre_x) + " " +
                                                   str(palette_items[index].pre_y) + " 0")
                    else:
                        del editor_section.value[editor_sec_index]
                        pal_section['Position'] = '999 999 999'
                        break
        
        return new_editor, self.data['vbsp']
    
class PalItem(ttk.Label):
    '''The icon and associated data for a single subitem.'''
    def __init__(self, frame, item, sub, is_pre):
        "Create a label to show an item onscreen."
        super().__init__(frame)
        self.item = item
        self.subKey = sub
        self.id = item.id
        self.visible=True # Toggled according to filter settings
        self.is_pre = is_pre # Used to distingush between picker and palette items
        self.load_data()
        self.bind("<Button-3>", contextWin.open_event)
        self.bind("<Button-1>", showDrag)
        self.bind("<Shift-Button-1>", fastDrag)
        self.bind("<Enter>", lambda e, n=self.name: setDispName(n))
        self.bind("<Leave>", clearDispName)
    
    def change_subtype(self, ind):
        '''Change the subtype of this icon, removing duplicates from the palette if needed.'''
        for item in pal_picked[:]:
            if item.id == self.id and item.subKey == ind:
                item.kill()
        self.subKey = ind
        self.load_data()
        self.master.update() # Update the frame
        flowPreview()
    
    def open_menu_at_sub(self, ind):
        '''Make the contextWin open itself at the indicated subitem on the item picker.'''
        if self.is_pre:
            items_list = pal_picked[:]
        else:
            items_list = []
        # Open on the palette, but also open on the item picker if needed
        for item in itertools.chain(items_list, pal_items):
            if item.id == self.id and item.subKey == ind:
                contextWin.showProps(item, warp_cursor=True)
                break
                
    def load_data(self):
        self.img = self.item.get_icon(self.subKey, self.is_pre)
        self.name = P2_trans(self.item.names[self.subKey])
        self['image'] = self.img
        
    def clear(self):
        '''Remove any items matching ourselves from the palette, to prevent adding two copies.'''
        found = False
        for i,item in enumerate(pal_picked[:]): 
        # remove the item off of the palette if it's on there, this lets you delete items and prevents having the same item twice.
            if self==item:
                item.kill()
                found = True
        return found
        
    def kill(self):
        '''Hide and destroy this widget.'''
        if self in pal_picked:
            pal_picked.remove(self)
        self.place_forget()
        self.destroy()
    
    def onPal(self):
        '''Determine if this item is on the palette.'''
        for item in pal_picked:
            if self==item:
                return True
        return False
        
    def __eq__(self, other):
        '''Two items are equal if they have the same overall item and sub-item index.'''
        return self.id == other.id and self.subKey == other.subKey
        
    def copy(self, frame):
        return PalItem(frame, self.item, self.subKey, self.is_pre)
        
    def __repr__(self):
        return '<' + str(self.id) + ":" + str(self.subKey) + '>'
        
class SubPane(Toplevel):
    '''A Toplevel window that can be shown/hidden, and follows the main window when moved.'''
    def __init__(self, parent, tool_frame, tool_img, tool_col=0, title='', resize_x=False, resize_y=False):
        self.visible=True
        self.allow_snap = True
        self.parent = parent
        self.relX = 0
        self.relY = 0
        super().__init__(parent)
        
        self.tool_button = ttk.Button(
            tool_frame, 
            style='BG.TButton', 
            image=tool_img, 
            command=self.toggle_win)
        self.tool_button.state(('pressed',))
        self.tool_button.grid(row=0, column=tool_col, padx=(5,2))
        
        self.transient(master=parent)
        self.resizable(resize_x, resize_y)
        self.title(title)
        self.iconbitmap('BEE2.ico')
        
        self.protocol("WM_DELETE_WINDOW", self.hide_win)
        parent.bind('<Configure>', self.follow_main, add='+')
        self.bind('<Configure>', self.snap_win)
        
    def hide_win(self):
        "Hide a window, effectively closes it without deleting the contents"
        snd.fx('config')
        self.withdraw()
        self.visible=False
        self.tool_button.state(('!pressed',))
        
    def toggle_win(self):
        if self.visible:
            self.hide_win()
        else:
            snd.fx('config')
            self.visible=True
            self.deiconify()
            self.parent.focus() # return focus back to main window so it doesn't flicker between if you press the various buttons
            self.tool_button.state(('pressed',))
            
    def move(self, x=None, y=None, width=None, height=None):
        '''Move the window to the specified position.
        
        Effectively an easier-to-use form of Toplevel.geometry(), that also updates relX and relY.
        '''
        if width is None:
            width = self.winfo_reqwidth()
        if height is None:
            height = self.winfo_reqheight()
        if x is None:
            x = self.winfo_x()
        if y is None:
            y = self.winfo_y()
        
        self.geometry(str(width) + 'x' + str(height) + '+' + str(x) + '+' + str(y))
        self.relX = x - self.parent.winfo_x()
        self.relY = y - self.parent.winfo_y()

    def snap_win(self, e=None):
        '''Callback for window movement, allows it to snap to the edge of the main window.'''
        # TODO: Actually snap to edges of main window
        if self.allow_snap:
            self.relX=self.winfo_x()-self.parent.winfo_x()
            self.relY=self.winfo_y()-self.parent.winfo_y()
            self.update_idletasks()

    def follow_main(self, e=None):
        '''When the main window moves, sub-windows should move with it.'''
        self.allow_snap=False
        self.geometry('+'+str(self.parent.winfo_x()+self.relX)+'+'+str(self.parent.winfo_y()+self.relY))
        self.allow_snap=True
        self.parent.focus()
        
def on_app_quit():
    '''Do a last-minute save of our config files.'''
    item_opts.save_check()
    gen_opts.save_check()
    win.destroy()
    
def load_palette(data):
    '''Import in all defined palettes.'''
    global palettes
    palettes=sorted(data,key=Palette.getName) # sort by name
    
def load_settings(settings):
    global gen_opts
    gen_opts = settings
    
def load_packages(data):
    '''Import in the list of items and styles from the packages.
    
    A lot of our other data is initialised here too. This must be called before initMain() can run.
    '''
    global item_list, skybox_win, voice_win, music_win, goo_win, style_win, filter_data, stylevar_list, selected_style
    filter_data = { 'package' : {},
                    'author' : {},
                    'tags' : {}}
                    
    for item in data['Item']:
        it = Item(item)
        item_list[it.id] = it
        for tag in it.tags:
            if tag.casefold() not in filter_data['tags']:
                filter_data['tags'][tag.casefold()] = tag
        for auth in it.authors:
            if auth.casefold() not in filter_data['author']:
                filter_data['author'][auth.casefold()] = auth 
        if it.pak_id not in filter_data['package']:
            filter_data['package'][it.pak_id] = it.pak_name 
        loader.step("IMG")
        
    stylevar_list = sorted(data['StyleVar'], key=lambda x: x.id)
    for var in stylevar_list:
        var.default = gen_opts.get_bool('StyleVar', var.id, var.default)
    sky_list = []
    voice_list = []
    style_list = []
    goo_list = []
    music_list = []
    
    obj_types  = [(sky_list, skyboxes, 'Skybox'),
                  (voice_list, voices, 'QuotePack'),
                  (style_list, styles, 'Style'),
                  (goo_list, goos, 'Goo'),
                  (music_list, musics, 'Music')
                 ]
    for sel_list, obj_list, name in obj_types:
        # Extract the display properties out of the object, and create a SelectorWin item to display with.
        for obj in sorted(data[name], key=lambda o: o.name):
            sel_list.append(selWinItem(
                    obj.id, 
                    obj.short_name,
                    longName = obj.name,
                    icon=obj.icon, 
                    authors=obj.auth, 
                    desc=obj.desc))
            obj_list[obj.id] = obj
            loader.step("IMG")
            
    skybox_win = selWin(
        win, 
        sky_list, 
        title='Select Skyboxes', 
        has_none=False,
        callback=selWin_callback,
        callback_params=['Skybox'])
        
    voice_win = selWin(
        win, 
        voice_list, 
        title='Select Additional Voice Lines', 
        has_none=True, 
        none_desc='Add no extra voice lines.',
        callback=selWin_callback,
        callback_params=['Voice'])
        
    music_win = selWin(
        win,
        music_list,
        title='Select Background Music',
        has_none=True,
        none_desc='Add no music to the map at all.',
        callback=selWin_callback,
        callback_params=['Music'])
        
    goo_win = selWin(
        win,
        goo_list,
        title='Select Goo Appearance',
        has_none=True,
        none_desc='Use a Bottomless Pit instead. This changes appearance'
                   'depending on the skybox that is chosen.',
        callback=selWin_callback,
        callback_params=['Goo'])
                   
    style_win = selWin(
        win, 
        style_list,
        title='Select Style',
        has_none=False,
        has_def=False)
                 
    last_style = gen_opts.get_val('Last_Selected', 'Style', 'BEE2_CLEAN')
    if last_style in style_win:
        style_win.sel_item_id(last_style)
        selected_style = last_style
    else:
        selected_style = 'BEE2_CLEAN'
        style_win.sel_item_id('BEE2_CLEAN')
    
    sugg = styles[selected_style].suggested
    obj_types = [(voice_win, 'Voice'),
                 (music_win, 'Music'),
                 (skybox_win, 'Skybox'),
                 (goo_win, 'Goo')]
    for (sel_win, opt_name), default in zip(obj_types, styles[selected_style].suggested):
        sel_win.sel_item_id(gen_opts.get_val('Last_Selected', opt_name, default))
    
def suggested_style_set(e=None):
    '''Set music, skybox, voices, goo, etc to the settings defined for a style.'''
    sugg = styles[selected_style].suggested
    win_types = (voice_win, music_win, skybox_win, goo_win)
    for win, sugg_val in zip(win_types, sugg):
        win.sel_item_id(sugg_val)
        
def style_select_callback(style_id):
    '''Callback whenever a new style is chosen.'''
    global selected_style
    selected_style = style_id
    gen_opts['Last_Selected']['Style'] = style_id
    for item in itertools.chain(item_list.values(), pal_picked, pal_items):
        item.load_data() # Refresh everything
    sugg = styles[selected_style].suggested
    win_types = (voice_win, music_win, skybox_win, goo_win)
    for win, sugg_val in zip(win_types, sugg):
        win.set_suggested(sugg_val)
    refresh_stylevars()
    
def selWin_callback(style_id, win_name):
    if style_id is None:
        style_id = '<NONE>'
    gen_opts['Last_Selected'][win_name] = style_id
    
def loadPalUI():
    "Update the UI to show the correct palettes."
    UI['palette'].delete(0, END)
    for i,pal in enumerate(palettes):
        UI['palette'].insert(i,pal.name)
    if menus['pal'].item_len>0:
        menus['pal'].delete(3, menus['pal'].item_len)
    menus['pal'].item_len=0
    for val,pal in enumerate(palettes): # Add a set of options to pick the palette into the menu system
        menus['pal'].add_radiobutton(label=pal.name, variable=selectedPalette_radio, value=val, command=setPal_radio)
        menus['pal'].item_len+=1
    
def export_editoritems(e=None):
    '''Export the selected Items and Style into the chosen game.'''
    gameMan.selected_game.export(
        styles[selected_style], 
        item_list, 
        music=musics.get(music_win.chosen_id, None),
        skybox=skyboxes.get(skybox_win.chosen_id, None),
        goo=goos.get(goo_win.chosen_id, None),
        voice=voices.get(voice_win.chosen_id, None),
        styleVars=styleOptVars)
    messagebox.showinfo('BEEMOD2', message='Selected Items and Style successfully exported!')
    if not gen_opts.get_bool('General','preserve_BEE2_resource_dir'):
        print('Copying resources...')
        gameMan.selected_game.refresh_cache()
        print('Done!')

def setPalette():
    print("Palette chosen: ["+ str(selectedPalette) + "] = " + palettes[selectedPalette].name)
    # TODO: Update the listbox/menu to match, and reload the new palette.
    for item in pal_picked:
        item.kill()
    pal_picked.clear()
    for item, sub in palettes[selectedPalette].pos:
        if item in item_list.keys():
            pal_picked.append(PalItem(frames['preview'], item_list[item], sub, is_pre=True))
        else:
            print('Unknown item "' + item + '"!')
    flowPreview()
    
def set_stylevar(var):
    val = str(styleOptVars[var].get())
    print('Updating ' + var + '! (val = ' + val + ')')
    gen_opts['StyleVar'][var] = val

def setDispName(name):
    UI['pre_disp_name'].configure(text='Item: '+name)

def clearDispName(e=None):
    UI['pre_disp_name'].configure(text='')

def convScrToGrid(x,y):
    "Returns the location of the item hovered over on the preview pane."
    return ((x-UI['pre_bg_img'].winfo_rootx()-8)//65,
           (y-UI['pre_bg_img'].winfo_rooty()-32)//65)

def convScrToPos(x,y):
    "Returns the index of the item hovered over on the preview pane."
    return ((y-UI['pre_bg_img'].winfo_rooty()-32)//65)*4 +\
           ((x-UI['pre_bg_img'].winfo_rootx()-8)//65)

def showDrag(e):
    "Start dragging a palette item."
    global drag_onPal,drag_item, drag_passedPal
    drag_item=e.widget
    setDispName(drag_item.name)
    snd.fx('config')
    drag_passedPal=False
    if drag_item.is_pre: # is the cursor over the preview pane?
        ind=drag_item.pre_x+drag_item.pre_y*4
        drag_item.kill()
        drag_onPal=True
        for item in pal_picked:
            if item.id == drag_item.id:
                item.load_data()
        # When dragging off, switch to the single-only icon
        UI['drag_lbl']['image'] = drag_item.item.get_icon(drag_item.subKey, allow_single=False)
    else:
        drag_onPal=drag_item.onPal()
        UI['drag_lbl']['image'] = drag_item.item.get_icon(drag_item.subKey, allow_single=True, single_num=0)
    dragWin.deiconify()
    dragWin.lift(win)
    dragWin.grab_set_global() # grab makes this window the only one to receive mouse events, so it is guaranteed that it'll drop when the mouse is released.
    # NOTE: _global means no other programs can interact, make sure it's released eventually or you won't be able to quit!
    moveDrag(e) # move to correct position
    dragWin.bind("<B1-Motion>", moveDrag)
    dragWin.bind("<ButtonRelease-1>", hideDrag)
    UI['pre_sel_line'].lift()

def hideDrag(e):
    "User released the mouse button, complete the drag."
    global drag_item
    dragWin.withdraw()
    dragWin.unbind("<B1-Motion>")
    dragWin.grab_release()
    clearDispName()
    UI['pre_sel_line'].place_forget()
    snd.fx('config')

    pos_x,pos_y=convScrToGrid(e.x_root,e.y_root)
    ind=pos_x+pos_y*4

    if drag_passedPal: #this prevents a single click on the picker from clearing items off the palette
        drag_item.clear() # wipe duplicates off the palette first
        if pos_x>=0 and pos_y>=0 and pos_x<4 and pos_y<8: # is the cursor over the preview pane?
            newItem=drag_item.copy(frames['preview'])
            newItem.is_pre = True
            if ind>=len(pal_picked):
                pal_picked.append(newItem)
            else:
                pal_picked.insert(ind,newItem)
            if len(pal_picked) > 32: # delete the item - it's fallen off the palette
                pal_picked.pop().kill()
        else: # drop the item
            snd.fx('delete')
        flowPreview() # always refresh
    drag_item = None

def moveDrag(e):
    "Update the position of dragged items as they move around."
    global drag_passedPal
    setDispName(drag_item.name)
    dragWin.geometry('+'+str(e.x_root-32)+'+'+str(e.y_root-32))
    pos_x,pos_y=convScrToGrid(e.x_root,e.y_root)
    if pos_x>=0 and pos_y>=0 and pos_x<4 and pos_y<8:
        drag_passedPal=True
        dragWin.configure(cursor='plus')
        UI['pre_sel_line'].place(x=pos_x*65+3, y=pos_y*65+33)
    else:
        if drag_onPal and drag_passedPal:
            dragWin.configure(cursor='x_cursor')
        else:
            dragWin.configure(cursor='no')
        UI['pre_sel_line'].place_forget()

def fastDrag(e):
    "When shift-clicking an item will be immediately moved to the palette or deleted from it."
    pos_x,pos_y=convScrToGrid(e.x_root,e.y_root)
    e.widget.clear()
    if pos_x>=0 and pos_y>=0 and pos_x<4 and pos_y<9: # is the cursor over the preview pane?
        snd.fx('delete')
        e.widget.kill() # remove the clicked item
    else: # over the picker
        if len(pal_picked) < 32: # can't copy if there isn't room
            snd.fx('config')
            newItem=e.widget.copy(frames['preview'])
            newItem.is_pre=True
            pal_picked.append(newItem)
        else:
            snd.fx('error')
    flowPreview()

def setPal_listbox(e):
    global selectedPalette
    selectedPalette = int(UI['palette'].curselection()[0])
    selectedPalette_radio.set(selectedPalette)
    setPalette()

def setPal_radio():
    global selectedPalette
    selectedPalette = selectedPalette_radio.get()
    UI['palette'].selection_clear(0,len(palettes))
    UI['palette'].selection_set(selectedPalette)
    setPalette()

def pal_remTempText(e):
    if PalEntry.get() == PalEntry_TempText:
        PalEntry.set("")

def pal_addTempText(e):
    if PalEntry.get() == "":
        PalEntry.set(PalEntry_TempText)

def saveAs():
    name=""
    while True:
        name=simpledialog.askstring("BEE2 - Save Palette", "Enter a name:")
        if name in paletteReadOnly:
            messagebox.showinfo(icon="error", title="BEE2", message='The palette \"'+name+'\" cannot be overwritten. Choose another name.')
        elif name == None:
            return
        else:
            break
    savePal(name)

def save():
    pal=palettes[selectedPalette]
    if pal in paletteReadOnly:
        saveAs() # If it's readonly, prompt for a name and save somewhere else
    else:
        savePal(pal) # overwrite it

def menu_newPal():
    newPal(simpledialog.askstring("BEE2 - New Palette", "Enter a name:"))

def newPal_textbox(e):
    newPal(PalEntry.get())

def filterExpand(e):
    frames['filter_expanded'].grid(row=2, column=0, columnspan=3)
    frames['filter']['borderwidth']=4
    frames['filter'].expanded=True
    snd.fx('expand')
    flowPicker()

def filterContract(e):
    frames['filter_expanded'].grid_remove()
    frames['filter']['borderwidth']=0
    frames['filter'].expanded=False
    snd.fx('contract')
    flowPicker()

def updateFilters():
    # First update the 'all' checkboxes to make half-selected if not fully selected.
    for cat in FILTER_CATS: # do for each
        no_alt=True
        all_vars = iter(FilterVars[cat].values())
        value=next(all_vars).get() # Pull the first one to get the compare value, this will check if they are all the same
        for var in all_vars:
            if var.get() != value:
                FilterVars_all[cat].set(True) # force it to be true so when clicked it'll blank out all the checkboxes
                FilterBoxes_all[cat].state(['alternate']) # make it the half-selected state, since they don't match
                no_alt=False
                break
        if no_alt:
            FilterBoxes_all[cat].state(['!alternate']) # no alternate if they are all the same
            FilterVars_all[cat].set(value)
    for item in pal_items:
        item.visible = (
            any(FilterVars['author'][auth.casefold()].get() for auth in item.item.authors) and
            any(FilterVars['tags'][tag.casefold()].get() for tag in item.item.tags) and
            FilterVars['package'][item.item.pak_id].get())
    flowPicker()

def filterAllCallback(col):
    "sets all items in a category to true/false, then updates the item list."
    val = FilterVars_all[col].get()
    for i in FilterVars[col]:
        FilterVars[col][i].set(val)
    updateFilters()

# UI functions, each accepts the parent frame to place everything in. initMainWind generates the main frames that hold all the panes to make it easy to move them around if needed
def initPalette(f):
    palFrame=ttk.Frame(f)
    palFrame.grid(row=0, sticky="NSEW")
    palFrame.rowconfigure(0, weight=1)
    palFrame.columnconfigure(0, weight=1)
    f.rowconfigure(0, weight=1)

    UI['palette']=Listbox(palFrame, width=10)
    UI['palette'].grid(sticky="NSEW")
    UI['palette'].bind("<<ListboxSelect>>", setPal_listbox)
    UI['palette'].selection_set(0)

    palScroll=ttk.Scrollbar(palFrame, orient=VERTICAL, command=UI['palette'].yview)
    palScroll.grid(row=0,column=1, sticky="NS")
    UI['palette']['yscrollcommand']=palScroll.set

    UI['newBox']=ttk.Entry(f, textvariable=PalEntry)
    UI['newBox'].grid(row=1, sticky=S) # User types in and presses enter to create
    UI['newBox'].bind("<Return>", newPal_textbox)
    UI['newBox'].bind("<FocusIn>", pal_remTempText)
    UI['newBox'].bind("<FocusOut>", pal_addTempText)
    ttk.Button(f, text=" - ").grid(row=2, sticky="EWS") # Delete (we probably don't want to allow deleting "None" or "Portal 2")
    ttk.Sizegrip(f, cursor="sb_v_double_arrow").grid(row=3)
        
def initOption(f):
    f.columnconfigure(0,weight=1)
    ttk.Button(f, width=10, text="Save...", command=save).grid(row=0)
    ttk.Button(f, width=10, text="Save as...", command=saveAs).grid(row=1)
    ttk.Button(f, width=10, text="Export...", command=export_editoritems).grid(row=2, pady=(0, 10))

    props=ttk.LabelFrame(f, text="Properties", width="50")
    props.columnconfigure(1,weight=1)
    props.grid(row=3, sticky="EW")
    ttk.Sizegrip(props,cursor='sb_h_double_arrow').grid(row=2,column=3, sticky="NS")
    
    UI['suggested_style'] = ttk.Button(props, text="\u2193 Use Suggested \u2193", command=suggested_style_set)
    UI['suggested_style'].grid(row=1, column=1, sticky="EW")

    ttk.Label(props, text="Style: ").grid(row=0)
    ttk.Label(props, text="Music: ").grid(row=2)
    ttk.Label(props, text="Voice: ").grid(row=3)
    ttk.Label(props, text="Skybox: ").grid(row=4)
    ttk.Label(props, text="Goo: ").grid(row=5)
    
    style_win.init_display(props, row=0, column=1)
    music_win.init_display(props, row=2, column=1)
    voice_win.init_display(props, row=3, column=1)
    skybox_win.init_display(props, row=4, column=1)
    goo_win.init_display(props, row=5, column=1)

def initStyleOpt(f):
    global styleCheck, styleCheck_enabled, styleCheck_disabled, styleOptVars

    UI['style_can']=Canvas(f, highlightthickness=0)
    UI['style_can'].grid(sticky="NSEW") # need to use a canvas to allow scrolling
    f.rowconfigure(0, weight=1)

    scroll = ttk.Scrollbar(f, orient=VERTICAL, command=UI['style_can'].yview)
    scroll.grid(column=1, row=0, rowspan=2, sticky="NS")
    UI['style_can']['yscrollcommand'] = scroll.set
    canFrame=ttk.Frame(UI['style_can'])

    #This should automatically switch to match different styles
    frmAll=ttk.Labelframe(canFrame, text="All:")
    frmAll.grid(row=0, sticky="EW")

    frmChosen=ttk.Labelframe(canFrame, text="Selected Style:")
    frmChosen.grid(row=1, sticky="EW")

    frmOther=ttk.Labelframe(canFrame, text="Other Styles:")
    frmOther.grid(row=2, sticky="EW")
    
    # The labelFrames won't update correctly if they become totally empty, so add some invisible widgets to both.
    Frame(frmChosen).grid()
    Frame(frmOther).grid()

    for pos, (id, name, default) in enumerate(styleOptions):
        styleOptVars[id]=IntVar(value=
            gen_opts.get_bool('StyleVar', id, default))
        styleCheck[id]=ttk.Checkbutton(
            frmAll, 
            variable=styleOptVars[id], 
            text=name, 
            command=func_partial(set_stylevar, id)
            )
        styleCheck[id].grid(row=pos, column=0, sticky="W", padx=3)
        
    for var in stylevar_list:
        styleOptVars[var.id] = IntVar(value=var.default)
        args = {
            'variable' : styleOptVars[var.id],
            'text' : var.name,
            'command' : func_partial(set_stylevar, var.id)
               }
        styleCheck_enabled[var.id] = ttk.Checkbutton(frmChosen, **args)
        styleCheck_disabled[var.id] = ttk.Checkbutton(frmOther, **args)
        
    UI['style_can'].create_window(0, 0, window=canFrame, anchor="nw")
    UI['style_can'].update_idletasks()
    UI['style_can'].config(scrollregion=UI['style_can'].bbox(ALL), width=canFrame.winfo_reqwidth())
    ttk.Sizegrip(f, cursor="sb_v_double_arrow").grid(row=1, column=0)
    
def refresh_stylevars():
    en_row = 0
    dis_row = 0
    for var in stylevar_list:
        if selected_style in var.styles:
            styleCheck_enabled[var.id].grid(row=en_row,sticky="W", padx=3)
            styleCheck_disabled[var.id].grid_remove()
            en_row += 1
        else:
            styleCheck_enabled[var.id].grid_remove()
            styleCheck_disabled[var.id].grid(row=dis_row,sticky="W", padx=3)
            dis_row += 1

def flowPreview():
    "Position all the preview icons based on the array. Run to refresh if items are moved around."
    for i,item in enumerate(pal_picked):
        item.pre_x=i%4
        item.pre_y=i//4 # these can be referred to to figure out where it is
        item.place(x=(i%4*65+4),y=(i//4*65+32))
        item.load_data() # Check to see if this should use the single-icon
        item.lift()
    
    item_count = len(pal_picked)
    for ind, fake in enumerate(pal_picked_fake):
        if ind < item_count:
            fake.place_forget()
        else:
            fake.place(x=(ind%4*65+4),y=(ind//4*65+32))
            fake.lift()
    UI['pre_sel_line'].lift()

def initPreview(f):
    "Generate the preview pane which shows the items that will export to the palette."
    global pal_picked_fake
    previewImg  = png.loadPng('BEE2/menu')
    UI['pre_bg_img']=Label(f, bg=ItemsBG, image=previewImg)
    UI['pre_bg_img'].imgsave=previewImg #image with the ingame items palette, needs to be saved to stop garbage collection
    UI['pre_bg_img'].grid(row=0,column=0)

    UI['pre_disp_name']=ttk.Label(f, text="Item: Button", style='BG.TLabel')
    UI['pre_disp_name'].place(x=10,y=552)

    selImg=png.loadPng('BEE2/sel_bar')
    UI['pre_sel_line']=Label(f, bg="#F0F0F0", image=selImg, borderwidth=0, relief="solid")
    UI['pre_sel_line'].imgsave=selImg
    
    blank = png.loadPng('BEE2/blank')
    pal_picked_fake = [ttk.Label(frames['preview'], image=blank) for _ in range(32)]
    
    flowPreview()

def initPicker(f):
    global frmScroll, pal_canvas, pal_items_fake
    ttk.Label(f, text="All Items: ", anchor="center").grid(row=0, column=0, sticky="EW")
    cframe=ttk.Frame(f,borderwidth=4, relief="sunken")
    cframe.grid(row=1, column=0, sticky="NSEW")
    f.rowconfigure(1, weight=1)
    f.columnconfigure(0, weight=1)

    pal_canvas=Canvas(cframe)
    pal_canvas.grid(row=0, column=0, sticky="NSEW") # need to use a canvas to allow scrolling
    cframe.rowconfigure(0, weight=1)
    cframe.columnconfigure(0, weight=1)

    scroll = ttk.Scrollbar(cframe, orient=VERTICAL, command=pal_canvas.yview)
    scroll.grid(column=1, row=0, sticky="NS")
    pal_canvas['yscrollcommand'] = scroll.set

    frmScroll=ttk.Frame(pal_canvas) # add another frame inside to place labels on
    pal_canvas.create_window(1, 1, window=frmScroll, anchor="nw")
    for item in item_list.values():
        for i in range(0,item.num_sub):
            pal_items.append(PalItem(frmScroll, item, sub=i, is_pre=False))
    blank = png.loadPng('BEE2/blank')
    # NOTE - this will fail silently if someone has a monitor that can fit 51 columns or more (3250+ pixels just for the icons
    pal_items_fake = [ttk.Label(frmScroll, image=blank) for _ in range(0,50)]
    f.bind("<Configure>",flowPicker)

def flowPicker(e=None):
    '''Update the picker box so all items are positioned based on the current size, and update values so scrolling works correctly.
    
    Should be run (e arg is ignored) whenever the items change, or the window changes shape.
    '''
    global frmScroll, pal_items_fake
    frmScroll.update_idletasks()
    frmScroll['width']=pal_canvas.winfo_width()
    if frames['filter'].expanded:
        # Offset the icons so they aren't covered by the filter popup
        offset = max(frames['filter_expanded'].winfo_height() - (pal_canvas.winfo_rooty() - frames['filter_expanded'].winfo_rooty()) + 10,0)
    else:
        offset = 0
    width=(pal_canvas.winfo_width()-10) // 65
    if width <1:
        width=1 # we got way too small, prevent division by zero
    vis_items = [it for it in pal_items if it.visible]
    itemNum=len(vis_items)
    for i,item in enumerate(vis_items):
        item.is_pre=False
        item.place(x=((i%width) *65+1),y=((i//width)*65+offset+1))
    
    for item in (it for it in pal_items if not it.visible):
        item.place_forget()
            
    pal_canvas.config(scrollregion = (0, 0, width*65, math.ceil(itemNum/width)*65+offset+2))
    frmScroll['height']=(math.ceil(itemNum/width)*65+offset+2)

    # this adds extra blank items on the end to finish the grid nicely.
    for i,blank in enumerate(pal_items_fake):
        if i>=(itemNum%width) and i<width: # if this space is empty
            blank.place(x=((i%width)*65+1),y=(itemNum//width)*65+offset+1)
        else:
            blank.place_forget() # otherwise hide the fake item

def initFilterCol(cat, f):
    FilterBoxes[cat]={}
    FilterVars[cat]={}
    FilterVars_all[cat]=IntVar(value=1)

    FilterBoxes_all[cat]=ttk.Checkbutton(f, text='All', onvalue=1, offvalue=0,  command=lambda: filterAllCallback(cat), variable=FilterVars_all[cat]) # We pass along the name of the category, so the function can figure out what to change.
    FilterBoxes_all[cat].grid(row=1, column=0, sticky=W)
    
    for ind, (id, name) in enumerate(sorted(filter_data[cat].items(), key=lambda x:x[1])):
        FilterVars[cat][id]=IntVar(value=1)
        FilterBoxes[cat][id] = ttk.Checkbutton(f, text=name, command=updateFilters, variable=FilterVars[cat][id])
        FilterBoxes[cat][id]['variable']=FilterVars[cat][id]
        FilterBoxes[cat][id].grid(row=ind+2, column=0, sticky=W, padx=(4,0))
        if ind==0:
            FilterBoxes_all[cat].first_var = FilterVars[cat][id]

def initFilter(f):
    ttk.Label(f, text="Filters:", anchor="center").grid(row=0, column=0, columnspan=3, sticky="EW")
    f.columnconfigure(0, weight=1)
    f.columnconfigure(1, weight=1)
    f.columnconfigure(2, weight=1)
    f2=ttk.Frame(f)
    frames['filter_expanded']=f2
    # Not added to window, we add it below the others to expand the lists

    f.bind("<Enter>", filterExpand)
    f.bind("<Leave>", filterContract)

    auth=ttk.Labelframe(f2, text="Authors")
    auth.grid(row=2, column=0, sticky="NS")
    pack=ttk.Labelframe(f2, text="Packages")
    pack.grid(row=2, column=1, sticky="NS")
    tags=ttk.Labelframe(f2, text="Tags")
    tags.grid(row=2, column=2, sticky="NS")
    initFilterCol('author', auth)
    initFilterCol('package', pack)
    initFilterCol('tags', tags)


def initDragIcon(win):
    global dragWin
    dragWin=Toplevel(win)
    dragWin.overrideredirect(1) # this prevents stuff like the title bar, normal borders etc from appearing in this window.
    dragWin.resizable(False, False)
    dragWin.withdraw()
    dragWin.transient(master=win)
    dragWin.withdraw() # starts hidden
    UI['drag_lbl']=Label(dragWin, image=png.loadPng('BEE2/blank'))
    UI['drag_lbl'].grid(row=0, column=0)
    
def set_win_title(game):
    win.title('BEEMOD 2.4 - ' + game.name)

def initMenuBar(win):
    bar=Menu(win)
    win['menu']=bar
    win.option_add('*tearOff', False) #Suppress ability to make each menu a separate window - weird old TK behaviour

    menus['file']=Menu(bar, name='apple') #Name is used to make this the special 'BEE2' menu item on Mac
    bar.add_cascade(menu=menus['file'], label='File')
    menus['file'].add_command(label="Export", accelerator='Ctrl-E', command=export_editoritems)
    
    win.bind_all('<Control-e>', export_editoritems)
    
    menus['file'].add_command(label="Find Game")
    menus['file'].add_command(label="Remove Game")
    menus['file'].add_separator()
    if snd.initiallised:
        menus['file'].add_checkbutton(label="Mute Sounds", variable=muted, command=lambda: snd.setMute(muted.get()))
    menus['file'].add_command(label="Quit", command=win.destroy)
    menus['file'].add_separator()
    
    gameMan.add_menu_opts(menus['file'], set_win_title) # Add a set of options to pick the game into the menu system
    
    menus['pal']=Menu(bar)
    bar.add_cascade(menu=menus['pal'], label='Palette')
    menus['pal'].add_command(label='New...', command=menu_newPal)
    menus['pal'].add_command(label='Clear')
    menus['pal'].add_separator()
    menus['pal'].item_len=0 # custom attr used to decide how many items to remove when reloading the menu buttons
    

    menuHelp=Menu(bar, name='help') # Name for Mac-specific stuff
    bar.add_cascade(menu=menuHelp, label='Help')
    menuHelp.add_command(label='About') # Authors etc
    menuHelp.add_command(label='Quotes') # show the list of quotes

def initMain():
    '''Initialise all windows and panes.'''
    initMenuBar(win)
    win.maxsize(width=win.winfo_screenwidth(), height=win.winfo_screenheight())
    win.protocol("WM_DELETE_WINDOW", on_app_quit)
    UIbg=Frame(win, bg=ItemsBG)
    UIbg.grid(row=0,column=0, sticky=(N,S,E,W))
    win.columnconfigure(0, weight=1)
    win.rowconfigure(0, weight=1)
    UIbg.rowconfigure(0, weight=1)

    style=ttk.Style()
    style.configure('BG.TButton', background=ItemsBG) # Custom button style with correct background
    style.configure('Preview.TLabel', background='#F4F5F5') # Custom label style with correct background

    frames['preview']=Frame(UIbg, bg=ItemsBG)
    frames['preview'].grid(row=0, column=3, sticky="NW", padx=(2,5),pady=5)
    initPreview(frames['preview'])
    frames['preview'].update_idletasks()
    win.minsize(width=frames['preview'].winfo_reqwidth()+200,height=frames['preview'].winfo_reqheight()+5) # Prevent making the window smaller than the preview pane
    loader.step('UI')

    loader.step('UI')

    ttk.Separator(UIbg, orient=VERTICAL).grid(row=0, column=4, sticky="NS", padx=10, pady=10)

    pickSplitFrame=Frame(UIbg, bg=ItemsBG)
    pickSplitFrame.grid(row=0, column=5, sticky="NSEW", padx=5, pady=5)
    UIbg.columnconfigure(5, weight=1)

    frames['filter']=ttk.Frame(pickSplitFrame, padding=5, borderwidth=0, relief="raised")
    frames['filter'].place(x=0,y=0, relwidth=1) # This will sit on top of the palette section, spanning from left to right
    frames['filter'].expanded=False
    initFilter(frames['filter'])
    loader.step('UI')

    frames['picker']=ttk.Frame(pickSplitFrame, padding=(5,40,5,5), borderwidth=4, relief="raised")
    frames['picker'].grid(row=0, column=0, sticky="NSEW")
    pickSplitFrame.rowconfigure(0, weight=1)
    pickSplitFrame.columnconfigure(0, weight=1)
    initPicker(frames['picker'])
    loader.step('UI')

    frames['filter'].lift()
    
    frames['toolMenu']=Frame(frames['preview'], bg=ItemsBG, width=192, height=26, borderwidth=0)
    frames['toolMenu'].place(x=73, y=2)

    windows['pal']=SubPane(
        win, 
        title='Palettes', 
        resize_y=True, 
        tool_frame=frames['toolMenu'], 
        tool_img=png.loadPng('icons/win_pal'),
        tool_col=0)
    initPalette(windows['pal'])
    loader.step('UI')

    windows['opt']=SubPane(
        win,
        title='BEE2 - Options',
        resize_x=True,
        tool_frame=frames['toolMenu'],
        tool_img=png.loadPng('icons/win_opt'),
        tool_col=1)
    initOption(windows['opt'])
    loader.step('UI')

    windows['style']=SubPane(
        win, 
        title='BEE2 - Style Properties', 
        resize_y=True, 
        tool_frame=frames['toolMenu'], 
        tool_img=png.loadPng('icons/win_style'),
        tool_col=2)
    initStyleOpt(windows['style'])
    loader.step('UI')

    win.bind("<MouseWheel>", lambda e: pal_canvas.yview_scroll(int(-1*(e.delta/120)), "units")) # make scrollbar work globally
    win.bind("<Button-4>", lambda e: pal_canvas.yview_scroll(1, "units")) # needed for linux
    win.bind("<Button-5>", lambda e: pal_canvas.yview_scroll(-1, "units"))

    windows['style'].bind("<MouseWheel>", lambda e: UI['style_can'].yview_scroll(int(-1*(e.delta/120)), "units")) # make scrollbar work globally
    windows['style'].bind("<Button-4>", lambda e: UI['style_can'].yview_scroll(1, "units")) # needed for linux
    windows['style'].bind("<Button-5>", lambda e: UI['style_can'].yview_scroll(-1, "units"))

    win.bind("<Button-1>",contextWin.hideProps)
    windows['style'].bind("<Button-1>",contextWin.hideProps)
    windows['opt'].bind("<Button-1>",contextWin.hideProps)
    windows['pal'].bind("<Button-1>",contextWin.hideProps)
    
    setPalette()
    contextWin.init(win)
    initDragIcon(win)
    loader.step('UI')

    win.deiconify() # show it once we've loaded everything

    win.update_idletasks()
    windows['style'].update_idletasks()
    windows['opt'].update_idletasks()
    windows['pal'].update_idletasks()

    # move windows around to make it look nice on startup
    if(win.winfo_rootx() < windows['pal'].winfo_reqwidth() + 50): # move the main window if needed to allow room for palette
        win.geometry('+' + str(windows['pal'].winfo_reqwidth() + 50) + '+' + str(win.winfo_rooty()) )
    else:
        win.geometry('+' + str(win.winfo_rootx()) + '+' + str(win.winfo_rooty()) )
    win.update_idletasks()
    
    xpos = min(win.winfo_screenwidth() - windows['style'].winfo_reqwidth(),win.winfo_rootx() + win.winfo_reqwidth() + 25 )
   
    windows['pal'].move(
        x=(win.winfo_rootx()-windows['pal'].winfo_reqwidth() - 25),
        y=(win.winfo_rooty()-50),
        height=win.winfo_reqheight())
    windows['opt'].move(
        x=xpos, 
        y=win.winfo_rooty()-40,
        width=windows['style'].winfo_reqwidth())
    windows['style'].move(
        x=xpos, 
        y=win.winfo_rooty()+windows['opt'].winfo_reqheight() + 25)

    
    win.bind("<Configure>", contextWin.follow_main, add='+')

    loadPalUI()
    style_win.callback = style_select_callback
    style_select_callback(style_win.chosen_id)
    
event_loop = win.mainloop