(function(window) {

function LessWatch() {

	this.init = function() {

		this.server = { host: 'localhost', port: 9000, url: '/less_updates' };
		this.debug = 1

		this.file_pattern = /(?:https?:)?\/\/[\w\.-]+(\/.+\.(?:less|css|js))(?:\?(?:[\w&=_-]*&)*server=([\w\.-]+)?(?::([0-9]{3,})?)?(\/[\w\/_-]*)?(?:&|$)?)?/;

		// regexp for extracting the path+filename and the optional server=... definition from an url
		var domain = "(?:https?:)?//[\\w\\.-]+", 
			path = "(/.+\\.(?:less|css|js))", 
			params = "\\?(?:[\\w&=_-]*&)*", 
			server_info = "server=([\\w\\.-]+)?(?::([0-9]{3,})?)?(/[\\w/_-]*)?", 
			ending = "(?:&|$)?", 
			pattern = domain + path + "(?:" + params + server_info + ending + ")?"

		this.file_pattern = RegExp(pattern)
		// this.test_regexp(this.file_pattern, 5); // pattern, expected number of pieces

		var params = this.collect_files(), files = params[0]
		if (params[1])
			params[1].each(function(a) { if (a[1]) this.server[a[0]] = a[1]; }, this);

		this.setup_commands();
		this.setup_callbacks();
		this.connect();

	}

	this.collect_files = function() {

		var get_file_info = function(a, url) { return (url = a.href || a.src) && (a = url.match(this)) && a.slice(1); };

		var files = $A(document.getElementsByTagName('link')).map(get_file_info, this.file_pattern).filter(this.self), 
			server_info = files.filter(function(a) { return a && a.slice(1).any(); }).first(), 
			server_params = ['host', 'port', 'url'];

		files = files.map(function(a) { return a[0]; });
		if (server_info)
			server_info = server_info.slice(1).map(function(a, i) { return a && [server_params[i], a]; }).without(0);

		return [files, server_info];
	}

	this.match_file = function(file) {

	}

	this.add_command = function(cmd, f) { this.commands[cmd] = f; }

	this.command = function(cmd, file, content, message) {
		if (typeof cmd === 'string') cmd = [cmd]
		return this.commands[cmd[0]] ?
			this.commands[cmd[0]].apply(this, [cmd, file, content]) : 
			this.debug && this.log('unknown command "%s" for "%s"\n-- content:\n%s\n-- message:', cmd.join(' '), file, content, message);
	}

	this.setup_commands = function() {
		this.commands = {}

		this.add_command('message', function(cmd, file, content) {
			this.log(content);
		})

		this.add_command('reload_page', function(cmd, file, content) {
			window.location.reload();
		})

		this.add_command('reload_file', function(cmd, file, content) {
			var matches = function(a) { return (a.href || a.src || '').endsWith(file); }, 
				clone = function(a) {
					var e = document.createElement(a.tagName);
					$A(a.attributes).each(function(x, i) { e[x.name] = x.value; });
					e.className = (e.className || '') + ' reloaded';
					return e;
				}, 
				reload = function(a) {
					this.log('reloading %s %s', a.tagName.toLowerCase(), a.href || a.src);
					var e = clone(a);
					a.parentNode.replaceChild(e, a);
					this.onreload(e);
				}, 
				items = document.head.childElements().filter(matches).each(reload, this);
		})

		this.add_command('less_update', function(cmd, file, content) {
			if (content) this.less_update(file, content);
		})

		this.add_command('less_refresh', function(cmd, file, content) {
			if (!less) return this.log('cannot refresh ' + file + ', no less object found (is a less.js included?)')
			this.log('refreshing ' + file + (cmd[1] ? ' (it was ' + cmd[1] + ')' : ''));
			this.remove_existing_styles(file);
			if (less) less.refresh(1); // refresh has a reload flag
		})

	}

	this.setup_callbacks = function() {
		this.onreloads = {
			less: function(file, item) {
				// if (item.rel && item.rel === 'stylesheet/less') less.refresh(1);
				console.log(item);
				console.log(item.nextSibling);
				this.remove_existing_styles()
			}
		}
		this.onupdates = {
		}
	}

	this.call_event = function(event, item) {
		var file = item.href || item.src, ext = file.split('.').pop();
		this.log('on%s %s:', event, item.tagName.toLowerCase(), item);
		event = 'on' + event + 's';
		return this[event][ext] && this[event][ext].apply(this, [file, item]);
	}

	this.onreload = function(item) { return this.call_event('reload', item); }
	this.onupdate = function(item) { return this.call_event('update', item); }


	/// less and css-related stuff

	this.style_name = function(file, id) { return 'less-watch:' + file + (id ? ':' + id.replace(/ /g, '-') : ''); }

	this.styles_matching = function(file) {
		file = this.style_name(file)
		return $A(document.getElementsByTagName('style')).filter(function(a) { return a.id.startsWith(file); });
	}

	this.remove_existing_styles = function(file, id) {
		var styles = this.styles_matching(file, id);
		if (!id) return styles.each(function(a) { a.parentNode.removeChild(a); }).length

		var start = id + ' {\n', ending = "}\n";
		var has_this_id = function(a) { return a.textContent.indexOf('\n' + id) > -1 || a.textContent.slice(0, id.length) === id; }
		var cut_content = function(target) {
			var i = target.textContent.indexOf(start), 
				j = target.textContent.indexOf(ending, i);
			// console.log(('removing "' + start + '...' + ending + '" from ' + target.id).replace(/\n/g, '|'))
			target.textContent = target.textContent.slice(0, i) + target.textContent.slice(j);
		}
		styles.filter(has_this_id).each(cut_content)
	}

	this.less_update = function(file, styles) {
		var ref = this, parser = new less.Parser(), css, id

		id = styles.slice(0, styles.indexOf('{')).strip(); // css selector part
		this.remove_existing_styles(file, id)

		// prefix + less_file_name + css-selector-part
		// TODO: hashing?
		id = 'less-watch:' + file + id.replace(/ /g, '-')

		if (this.debug > 1)
			this.log('updating ' + file.slice(file.lastIndexOf('/') + 1) + ': ' + styles)
		parser.parse(styles, function(err, tree) { ref.parse(err, tree); });

		if (!this.css) return;

		if ((css = document.getElementById(id)) === null) {
			css = document.createElement('style');
			css.type = 'text/css';
			css.id = id;
			document.getElementsByTagName('head')[0].parentNode.insertBefore(css, null);
		}

		if (css.styleSheet) { // IE
			try {
				css.styleSheet.cssText = styles;
			} catch (e) {
				throw new(Error)("Couldn't reassign styleSheet.cssText.");
			}
		} else {
			(function (node) {
				if (!css.childNodes.length) css.appendChild(node);
				else if (css.firstChild.nodeValue !== node.nodeValue) css.replaceChild(node, css.firstChild);
			})(document.createTextNode(styles));
		}
	}

	this.parse = function(err, tree) {
		this.css = '';
		if (err) return this.log(err.message + ' (column ' + err.index + ')');
		this.css = tree.toCSS();
	}



	/// websocket stuff

	this.connect = function() {
		var url = "ws://" + this.server.host + ':' + this.server.port + this.server.url + '?client=' + window.location.href;

		this.log('connecting to ' + url.split('?')[0]);
		var ref = this, socket = this.socket = new WebSocket(url); 

		var methods = [
			function onopen() {
				var files = this.files.map(function(a) { return a.replace(/https?:\/\/[\w\.-]+/, ''); });
				this.log('watching ' + files.join(', '));
				this.socket.send('watch\n' + files.join('\n'))
			},

			function onclose() { this.log('websocket closed'); },

			function onmessage(message) {
				if (this.debug > 1) this.log(message)

				var tmp = message.data.split('\n', 2), 
					content = message.data.slice(tmp[0].length + tmp[1].length + 2), 
					file = tmp[0], 
					cmd = (tmp[1] || '').strip(), 
					single_arg = cmd.length && cmd.indexOf('"') > -1 && cmd.indexOf(' ');

				// false: no '"' -- split by spaces
				// 0 (no length) or -1 (no space) -- single array
				// else: split by first space, let the command method sort out arguments
				cmd = single_arg === false ? 
					cmd.split(' ').without('') :
					(single_arg <= 0 ? [cmd] : [cmd.slice(0, single_arg), cmd.slice(single_arg + 1)])

				this.command(cmd, file, content, message);

			}
		]

		methods.each(function(func) { socket[func.name] = function() { func.apply(ref, arguments); } });

		return this.socket;
	}

	this.reconnect = function(server) {
		if (server) this.server = server
		return (this.socket && this.socket.close()) || this.connect();
	}



	/// utilities

	this.hash = function(str) {
		var hash = 0, letter;
		if (str.length === 0) return hash;
		for (i = 0; i < str.length; i++) {
			letter = str.charCodeAt(i);
			hash = ((hash<<5) - hash) + letter;
			hash = hash & hash; // Convert to 32bit integer
		}
		return hash;
	}

	this.log = function() {
		if (!this.debug || !arguments.length) return;

		// add a prefix, attached to the first argument if it's a string
		var prefix = '[less-watch ' + (new Date()).toTimeString().slice(0, 8) + '] ',
			add = (typeof arguments[0] === 'string' ? 1 : 0)
			args = [prefix + (add ? arguments[0] : '')].concat(Array.prototype.slice.call(arguments, add));
		return console.log.apply(console, args);

		// for non-console logging
		// return this.somemethod(this.format.apply(this, args));
	}

	// for non-console messages, something like this could be used in the same format as console.log
	// TODO: add proper %d, %f, %i, maybe %o
	this.format = function() {
		if (arguments.length < 2) return arguments[0];
		var args = arguments;
		return $A(args[0].split('%s')).reduce(function(res, a, i) {
			// console.log('item ' + i + ': "' + a + '", args[' + i + ']: "' + args[i] + '", current result: "' + res + '"')
			return res + (i ? (args[i] === undefined ? '(?)' : args[i]) : '') + a;
		}, '');
	}

	this.self = function(x) { return x; }

	this.test_regexp = function(file_pattern, expected) {
		var protocols = [
			'http://',
			'https://',
			'//'
		]
		var domains = [
			"localhost", 
			"127.0.0.1", 
			"some.domain.com", 
		]
		var paths = [
			'simple/', 
			'some/path/', 
			'some_more-paths/', 
			'some_more-paths/qu%20te/long/-in/fact/', 
			'/'
		]
		var files = [
			'som-e.js',
			'silly_named_.css',
			'A12FU_1a.less'
		]
		var params = [
			'simple=1', 
			'some=more&vars=__3', 
			'some_illegal_too'
		]
		var hosts = ['some-server-host', '']
		var ports = [':9000', ':', '']
		var urls = ['/some_url/path', '/', '']

		var generate = function(list, prefix) {
			return function (a) { return list.map(function(x) { return a + prefix + x; }); };
		}
		var flatten = function(list, prefix) {
			return function (a) {  }
			return generate(list, prefix).flatten();
		}

		// paths get a '/' prefix; query params a '?'; etc

		var result = $A(protocols).
			map(generate(domains, '')).flatten().
			map(generate(paths, '/')).flatten().
			map(generate(files, '')).flatten().
			map(generate(params, '?')).flatten().
			map(generate(hosts, '&server=')).flatten().
			map(generate(ports, '')).flatten().
			map(generate(urls, '')).flatten();

		// return a specific item, if asked
		if (expected < 0) return [result[-expected]];

		var errors = result.filter(function(a) { return (a.match(file_pattern) || []).length !== expected; });

		// console.log(file_pattern)
		// console.log((result[0].match(file_pattern) || []).join('\n'))

		console.log('file pattern test: %s/%s errors%s', errors.length, result.length, 
			(errors.length || '') && ', example: ' + errors[0] + '\n' + (errors[0].match(file_pattern) || []).join('\n'))
		return !errors;
	}

	this.init();
	return this;

}

return window.watch = new LessWatch();

})(window);
