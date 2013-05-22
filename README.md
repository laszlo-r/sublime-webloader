
Webloader - a Sublime Text 2 plugin
===================================

Updates css/less _live as you type_, or reloads the page when saving js/html/php.

Uses websockets, works without a webserver, with multiple pages or files at once. You can run javascript on a page directly from Sublime, define custom actions when you edit/save/load, or add more file extensions. Nothing else to install but the plugin.

__Still very much in development, but suggestions and fixes are welcome.__

How to use:
-----------
- install with Package Control: `ctrl-shift-p`, `Package Control: Install Package`, `Webloader`
- restart Sublime, and go to the plugin's directory:
  - windows: `userfolder\AppData\Roaming\Sublime Text 2\Packages\Webloader`
  - os x: `~/Library/Application Support/Sublime Text 2/Webloader`
  - linux: `~/.config/sublime-text-2/Webloader`
- if you have a local webserver, copy the `demo` directory under your webroot (if you don't, skip this)
- open `demo/index.html` in a browser (if no webserver, open it as `file://`)
- edit `demo.css` with Sublime, and see the changes on the page *as you type*
- edit `index.html`, add some text, save it - this should refresh the page
- if you used a webserver, try editing `demo.less`, it should update live too!

Used in your projects:
----------------------
- __in one line__: install the plugin, and include webloader.js on your page (if you use .less files, add less.js too)
- webloader.js works standalone, no js framework necessary (less.js is optional; tested with less-1.3.3)
- non-localhost websites:
  - if the page is not on your machine, or sees you as a different ip than localhost/127.0.0.1/::1
  - define your ip: `<script src='webloader.js?server=192.168.0.100:9000'></script>`
  - and you may have to enable this port in your firewall
- check out the settings in the `Packages/Webloader/Webloader.sublime-settings` file:
  - server: if you want to change the above port
  - clients: if you do not trust your lan, or opened the above port to the wide internet
  - save\_parsed\_less: if you want to enable converting `.less` to `.css` on save
  - watch_events: if you want to add or remove file types
  - sites: if you use virthosts, symlink directories to your docroot, or similar
- you can refresh the browser _from Sublime_ with `F5` (use `ctrl-shift-j` to select between multiple pages)
- you can run javascript on a page directly from Sublime with `ctrl-shift-j`
- you can send commands to the server with `ctrl-shift-c` (currently only supports stop/restart/start)
- if you feel like hacking around, you can add custom actions to `webloader.js` (or even `webloader.py`):
  - the `setup_commands` and `setup_callbacks` show the default actions, feel free to customize these
  - you can mess around with the code however you like for your own purposes, but you can't distribute it

Future plans:
-------------
- more polished codebase, as I'm still changing it around daily
- simpler and easier customization and actions
- I may release under a less restrictive license later, when I feel it's ready

Contact and terms:
------------------
- Contact: <http://rozsahegyi.info>
- Project: <https://github.com/rozsahegyi/sublime-webloader>
- License: [Creative Commons Attribution-NonCommercial-NoDerivs 3.0 Unported License][license].
- Summary: free to download/share/use, but you have to credit me, and you can't sell, alter, or bundle this.
- ![Creative Commons License][image]

Credits:
--------
- plugin code on the [sublime API] and standard python library
- uses [less.js] for compiling .less files



  [sublime API]: http://www.sublimetext.com/docs/2/api_reference.html
  [less.js]: http://lesscss.org/
  [image]: http://i.creativecommons.org/l/by-nc-nd/3.0/88x31.png
  [license]: http://creativecommons.org/licenses/by-nc-nd/3.0/
