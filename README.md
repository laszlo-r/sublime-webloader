
Webloader - a Sublime Text 2 plugin
===================================

Updates css/less on a page _live as you type_, or when saving js/html/php.

Uses websockets, works without a webserver, with multiple pages or files at once. You can run javascript on a page directly from Sublime, define custom actions when you edit/save/load, or add more file extensions. Nothing else to install but the plugin.

__Still very much in development, but suggestions and fixes are welcome.__

How to use:
-----------
- no package control yet, but it's quite easy to install manually:
  - download as zip, unzip, and move the Webloader folder under your Sublime Packages folder
  - windows: `youruserfolder\AppData\Roaming\Sublime Text 2\Packages`
  - os x: `~/Library/Application Support/Sublime Text 2`
  - linux: `~/.config/sublime-text-2`
  - restart Sublime (the console should show a `[Webloader]` message if the plugin loaded)
- open `Webloader/demo/index.html` in a browser (the javascript console shows if it's connected to the plugin)
- edit `sample.css` with Sublime, and see the changes on the page *as you type*
- open `index.html` with Sublime, and save it, this should refresh the page
- if you put this under your webserver, opening it as http://.../index.html, `.less` files can be updated live too!

Used in your projects:
----------------------
- include a less.js, a prototype.js, and the webloader.js (works with the included versions)
- be sure to put webloader.js __after__ any link or script tags you want to keep updated!
- if the web page is not on your machine, or sees you as a different ip than localhost/127.0.0.1/::1
  - include the script like this: `<script src='webloader.js?server=192.168.0.100:9000'></script>`
  - and you may have to enable this port (you can change it) in your firewall
- check out the settings in the Packages/Webloader/Webloader.sublime-settings file:
  - see the 'clients' setting if you do not trust your lan, or opened the above port
  - see the 'watch_events' setting if you want to add or remove file types
  - see the 'sites' setting if you use virthosts, symlink your directories to your docroot, or similar
  - not everything is supported fully yet, but this should be mentioned in the comments
- you can run javascript on the page directly from Sublime with ctrl-shift-j
- you can send commands to the server with ctrl-shift-c (currently only supports stop/restart/start)

Future plans:
-------------
- submit to package control
- more polished codebase, as I'm still changing it around daily
- more/simpler options and Sublime file-actions
- I may release under a less restrictive license later, when I feel it's ready

License:
--------
- Contact: <http://rozsahegyi.info>
- License: [Creative Commons Attribution-NonCommercial-NoDerivs 3.0 Unported License][license].
- Summary: free to download/share/use, you have to credit me, and you can't sell it or build upon it.
- ![Creative Commons License][image]

Credits:
--------
- plugin code on the [sublime API] and standard python library
- uses less.js for compiling [lesscss.org], and [prototype] for simplifying life



  [sublime API]: http://www.sublimetext.com/docs/2/api_reference.html
  [lesscss.org]: http://lesscss.org/
  [prototype]: http://prototypejs.org/
  [image]: http://i.creativecommons.org/l/by-nc-nd/3.0/88x31.png
  [license]: http://creativecommons.org/licenses/by-nc-nd/3.0/
