
TODO:
-----
- test utf8 characters in urls and paths, test linux paths (currently first bit removed with paths like file:///C:/)
- test various sites settings, virthosts, symlinked paths, etc
- hotkey for page reload for the selected/single client; definitely, page reloading on every save may be annoying and slow for some
- add menu items for options and commands
- currently clients can call self.server, which could have exited and been deleted meanwhile
- use standard logging
- submit to package control <http://wbond.net/sublime_packages/package_control/package_developers>
- revisit and test bigger css updates, like whole less blocks, fix selector updates (not updated on edit, only with saving)
  - faster updates: could only send the current key-value pair, between previous and next semicolons or brackets, maybe validate them
  - multiple selections: with less you probably factor out frequently used values into variables, so not a priority
  - a full refresh would be is necessary, which is slow with large files + typing; could timeout for 0.5-1sec when multiple selections
- lesscss is apache 2 licensed (free, include all credits), prototype is MIT (free)

Simple changelog
----------------
+ file urls can be urlencoded, also test file:/// mode; seems to work with (ascii) escaped urls
+ implement clients setting; set ip limit on clients to prevent flooding/hacks
+ implement save_parsed_less: find the less file in client.files; save the parsed content beside it as .css; has to be enabled in settings!
+ complete js command: quick panel if multiple clients, send to selected (or current) client
+ server command: start/stop/restart; also sends 'cmd file multi line content' to all clients
+ implement sites setting; work with the examples listed in the settings file
+ when changing settings, plugin should notice, and clients should update their patterns; implemented for important settings
+ webloader.js runs on dom:loaded, can be put anywhere on the page
+ converting less: less parser now gets a rootpath (prefixes url()), which is the relative path between the page and the less file
+ update readme
+ server and websocket now build upon SocketServer classes, using select()

Matching
--------

	except for the index page, we can't know what the project's dir is, but if we find the common part (if any)
	in page and reference urls, we can match html and php (or any type) files to that
		current page: */ or */some/page
		linked file:  */media/some.css
		other linked: */js/some.js
		if localhost: * + file paths -> /basepath/some/page(page|filepath)
		if virthost:  /virthost.com* + file paths -> /virthost.com/basepath/(page|filepath)

	"sites", aka user-defined pathname -> url combinations, if either:
		- different directory name and virthost
		- user-friendly urls, redirects, hiding direct .php and .html access
		- folders/files symlinked to docroot, but editing files in the original location
		- various templates which obviously won't match directly to urls

			/www/mywebdir/projectname/* -> customvirthost:8080/*
			/totally/different/folder/* -> domain.com/website/subpages/*
