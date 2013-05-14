(function(window) {

function WebLoader() {

	if (!String.prototype.endsWith) {
		String.prototype.startsWith = function(x) { return this.slice(0, x.length) === x; }
		String.prototype.endsWith = function(x) { return this.slice(-x.length) === x; }
	}

	this.init = function() {
		this.server = { host: 'localhost', port: 9000, re_min_interval: 15, re_timer: 0 };
		this.debug = 1;

		this.collect_files();
		this.setup_commands();
		this.setup_callbacks();

		this.connect();
	}

	this.collect_files = function() {
		// regexps for extracting the path+filename and the optional server=... definition from an url
		// var domain = "(?:https?:)?//[\\w\\.-]+",
		var domain = "(?:(?:(?:https?:)?//[\\w\\.-]+)(?::[0-9]+)?|(?:file:///[\\w:]+))",
			path = "(/.+\\.(?:less|css|js))",
			params = "\\?(?:[\\w&:=_-]*&)*",
			server_param = "server=([\\w\\.-]+)?(?::([0-9]{3,})?)?(/[\\w/_-]*)?",
			ending = "(?:&|$)?",
			pattern = domain + path + "(?:" + params + server_param + ending + ")?"

		this.file_pattern = RegExp(pattern)
		// this.test_regexp(this.file_pattern, 5); // pattern, expected number of pieces

		var get_file_info = function(a) { return (a = a.href || a.src) && (a = a.match(this)) && a.slice(1); },
			files = this.array(document.head.children).map(get_file_info, this.file_pattern).filter(this.is_true);

		this.check_server_params(files);

		this.files = files.map(function(a) { return a[0]; });
	}

	this.check_server_params = function(files) {
		var server_params = ['host', 'port'],
			scriptname = '/webloader.js';

		var param_name = function(x, i) { return x && [server_params[i], x]; },
			defined = function(a) { return !!a; },
			get_params = function(a) { return a && a[0] && a[0].endsWith(scriptname) && a.slice(1).map(param_name).filter(defined); },
			add_params = function(a) { if (a && a[1]) this[a[0]] = a[1]; };

		(files.map(get_params).filter(this.is_true).shift() || []).map(add_params, this.server);
	}

	this.request_watching = function() {
		if (this.debug > 1) this.log('watching ' + this.files.join(', '));
		else this.log('watching ' + this.files.map(function(a) { return a.slice(a.lastIndexOf('/') + 1); }).join(', '));
		// this.socket.send('watch\n' + this.files.join('\n'))
		this.send_command('watch', null, this.files);
	}

	// file can be an element with href or src, or a file handle from this.files (even a partial match)
	// returns the basepath + filename + extension like this:
	// "http://domain.com/some/path/this.file?with=params" -> "/some/path/this.file"
	this.file_handle = function(file) {
		if (typeof file !== 'string') file = file.href || file.src;
		if (file.indexOf('//') > -1) return (file = file.match(this.file_pattern)) && file[1] || '';
		return this.files.filter(function(a) { return a.endsWith(file); }).shift() || ''
	}

	this.file_element = function(filehandle) {
		if (!filehandle.startsWith('/')) filehandle = this.file_handle(filehandle)
		var matches = function(a) { return (a.href || a.src || '').split('?')[0].endsWith(filehandle); };
		return this.array(document.head.children).filter(matches).shift();
	}

	this.send_command = function(cmd, file, content) {
		if (!cmd) return false
		return this.socket.send(JSON.stringify({ cmd: cmd, filename: file || '', content: content || '' }));
	}

	this.parse_command = function(message) {
		if (this.debug > 2) this.log(message)

		try {
			message = JSON.parse(message.data) || {};
		} catch (e) {
			this.log('error parsing message: %s\n--message:', e, message)
			if (!cmd || typeof cmd != 'string') return this.log('unknown message:', message)
		}
		var cmd = message.cmd,
			file = message.filename || '',
			content = message.content || '',
			single_arg = cmd.length && cmd.indexOf('"') > -1 && cmd.indexOf(' ');

		// examine the command line:
		// false: no '"' -- split by spaces
		// 0 (no length) or -1 (no space) -- single array
		// else: split by first space, let the command method sort out arguments

		cmd = single_arg === false ?
			cmd.split(' ').filter(this.is_true) :
			(single_arg <= 0 ? [cmd] : [cmd.slice(0, single_arg), cmd.slice(single_arg + 1)])

		this.command(cmd, file, content, message);
	}

	this.command = function(cmd, file, content, message) {
		var item = file && typeof file === 'string' ? this.file_element(file) : file;
		if (typeof cmd === 'string') cmd = [cmd];

		if (!this.commands[cmd[0]] || this.debug > 1)
			this.log((!this.commands[cmd[0]] ? 'unknown ' : '') +
				'command "%s" (%s)\n-- file: "%s"\n-- content (%s):\n%s-- message:',
				cmd.join(' '), Object.keys(message).join(', '), file, content.length,
				(content ? content.slice(0, 100).replace('\n', '\\n\n') + '\n...' : ''), message);
		return this.commands[cmd[0]] ? this.commands[cmd[0]].apply(this, [cmd, item || file, content]) : null;
	}

	this.add_command = function(cmd, f) { this.commands[cmd] = f; }

	this.setup_commands = function() {
		this.commands = {}

		this.add_command('message', function(cmd, file, content) {
			this.log(content);
		})

		this.add_command('reload_page', function(cmd, file, content) {
			window.location.reload();
		})

		this.add_command('reload_file', function(cmd, file, content) {
			if (!file || (!file.href && !file.src)) return this.log('cannot find the element for "%s"', file)
			if (file.src && file.src.split('/').pop().split('?')[0] === 'webloader.js') {
				this.server.re_min_interval = 0;
				this.socket && this.socket.close();
			}

			var clone = function(a) {
				var e = document.createElement(a.tagName),
					attr = (a.href ? 'href' : 'src'),
					skey = 'reloaded=',
					stamp = skey + this.stime();
				Array.prototype.slice.call(a.attributes, 0).map(function(x, i) { e[x.name] = x.value; });
				e.className += (e.className ? ' ' : '') + stamp.replace('=', ':');
				var tail = e[attr].slice(-(stamp.length + 1));
				if (tail.startsWith('?' + skey) || tail.startsWith('&' + skey)) e[attr] = e[attr].slice(0, -(stamp.length + 1));
				e[attr] += (e[attr].indexOf('?') > -1 ? '&' : '?') + stamp;
				return e;
			}

			var twin = clone.apply(this, [file]);
			this.log('reloading %s %s (%s)', twin.tagName.toLowerCase(), twin.href || twin.src, cmd[1] || 'no reason');
			file.parentNode.replaceChild(twin, file);
			this.onreload(twin, cmd);
		})

		var reload_file = function(cmd, file, content) {
			this.command(['reload_file', 'was ' + cmd[0]], file)
		}

		this.add_command('opened', reload_file); // see an updated page before editing
		this.add_command('closed', reload_file); // remove changes from cancelled edits
		this.add_command('saved', reload_file);  // reload a freshly saved file

		this.add_command('update', function(cmd, file, content) {
			if (file.type === 'text/css' && content) this.css_update(file, content);
			else console.log(cmd, file, content);
		})

		this.add_command('run', function(cmd, file, content) {
			if (content && content.length) {
				var result = eval(content);
				console.log(result);
				this.send_command('js_results', content, this.inspect(result));
			}
		})
	}

	this.setup_callbacks = function() {
		this.onreloads = {
			'*': function(item, file, cmd) {
				var len = this.stime().length, attr = item.href ? 'href' : 'src', url = item[attr];
				// reserved for later
			},
			less: function(item, file, cmd) {
				if (!item || item.type !== 'text/css') return;

				var ref = this, style = item.nextElementSibling, url = item.href;

				if (!this.is_less(item)) return;

				var onFailure = function(response) {
						ref.log('could not refresh %s!', url);
					},
					onSuccess = function(response) {
						if (ref.debug > 1) ref.log('ajax: updating %s with', url, response);
						var parsed = ref.less_parse(response.responseText, item, 1);
						style.textContent = parsed;
						if (cmd && cmd[1] === 'save_parsed_less') {
							// parse again without rootpath (in a css, url() paths should be relative to the css file)
							parsed = ref.less_parse(response.responseText, item);
							ref.send_command('parsed_less', ref.file_handle(file), parsed);
						}
					};
				this.ajax_request(url, { failure: onFailure, success: onSuccess });
			}
		}
		this.onreloads.css = this.onreloads.less;

		this.onupdates = {
		}
	}

	this.call_event = function(event, item, cmd) {
		var file = this.file_handle(item), ext = file.split('.').pop();
		if (this.debug > 1)
			this.log('on%s %s:', event, item.tagName.toLowerCase(), item);
		event = 'on' + event + 's';
		this[event]['*'].apply(this, [item, file, cmd]);
		return this[event][ext] && this[event][ext].apply(this, [item, file, cmd]);
	}

	this.onreload = function(item, cmd) { return this.call_event('reload', item, cmd); }
	this.onupdate = function(item, cmd) { return this.call_event('update', item, cmd); }


	this.ajax_request = function(url, callbacks) {
		var req = new XMLHttpRequest();
		req.onreadystatechange = function() {
			if (req.readyState !== 4) return;
			var status = req.status,
				success = status >= 200 && status < 300,
				callback = callbacks[success ? 'success' : 'failure'] || function(response) {};
			callback(req);
		}
		req.open('POST', url);
		req.send();
	}


	/// less and css-related stuff

	this.relative_css_path = function(item) {
		var page = document.baseURI, path = item.href, arr = [page.split('/'), path.split('/')];
		for (var i = 0; i < arr[0].length - 1; i++)
			if (arr[0][i] !== arr[1][i]) break;
		return (new Array(arr[0].length - i)).join('../') + (arr[1].slice(i, -1).concat([''])).join('/');
	}

	this.is_less = function(item) {
		// less files should have a .less extension and stylesheet/less declared
		var file = item.href.split('?')[0];
		return file.slice(file.lastIndexOf('.') + 1) === 'less' && item.rel && item.rel === 'stylesheet/less';
	}

	this.less_handle = function(file) {
		file = this.file_handle(file);
		return file && (file.endsWith('.css') ? 'css:' : 'less:') + file.replace(/[^\w\.-]+/g, '-').slice(1, file.lastIndexOf('.'));
	}

	this.less_element = function(file) {
		var handle = this.less_handle(file);
		return this.array(document.getElementsByTagName('style')).filter(function(a) { return a.id.startsWith(handle); }).shift();
	}

	this.css_update = function(file, styles) {
		var handle = this.file_handle(file),
			id = this.less_handle(handle),
			sheet = this.less_element(handle),
			is_less = id.startsWith('less:'), css, next

		// disable the original element's rules; add the file's path to url() definitions
		if (!is_less) {
			file.disabled = true;
			styles = styles.replace(/(\Wurl\(\s*)(?=[^\/])/g, "$1" + this.relative_css_path(file));
		} else
			styles = this.less_parse(styles, file);

		if (typeof styles !== 'string') return;
		if (this.debug > 1)
			this.log('updating "%s", style id "%s"', handle.slice(handle.lastIndexOf('/') + 1), id)

		// lookup or make a style element, put after the "less:" element
		if (!(css = document.getElementById(id))) {
			css = document.createElement('style');
			css.type = 'text/css';
			css.id = id;
			next = (next = file.nextSibling) && next.id && next.id.startsWith('less:') ? next.nextSibling : next;
			file.parentNode.insertBefore(css, next);
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

	this.less_parse = function(styles, fileelem, setpath) {
		if (!less || !less.Parser) return this.log('no less object found, is a less.js included?');
		var err, result,
			env = setpath ? { rootpath: this.relative_css_path(fileelem) } : {},
			parser = new less.Parser(env);
		parser.parse(styles, function(err, tree) { result = [err, tree]; });
		return (err = result[0]) ?
			(this.debug > 1 && this.log('less parser: ' + err.message + ' (column ' + err.index + ')')) :
			result[1].toCSS();
	}



	/// websocket stuff

	this.connect = function() {
		var url = "ws://" + this.server.host + ':' + this.server.port + '?client=' + window.location.href.split('#')[0];

		if (this.socket === undefined) this.log('connecting to server at ' + url.split('?')[0]);
		var ref = this, socket = this.socket = new WebSocket(url);

		var methods = [
			function onopen() {
				this.server.re_timer = 0;
				this.request_watching();
			},
			function onclose() {
				if (!this.server.re_min_interval) return this.log('connection closed, and reconnecting is turned off.');
				if (!this.server.re_timer) this.log('connection closed, running reconnect attempts...');
				this.reconnect(0);
				this.socket = null;
			},
			function onmessage(message) {
				this.parse_command(message);
			}
		]

		methods.map(function(func) { socket[func.name] = function() { func.apply(ref, arguments); } });

		return this.socket;
	}

	this.reconnect = function(server, after) {
		if (!this.server.re_min_interval) return
		if (server) this.server = server;
		var ref = this, attempt = function() {
			return (ref.socket && ref.socket.close()) || ref.connect();
		}
		if (after === undefined)
			after = this.server.re_timer = Math.min((Number(this.server.re_timer) || 0) + 1, this.server.re_min_interval)
		setTimeout(attempt, after * 1000);
		return after;
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

	this.stime = function() { return (new Date()).toTimeString().slice(0, 8); }

	this.log = function() {
		if (!this.debug || !arguments.length) return;

		// add a prefix, attached to the first argument if it's a string
		var prefix = '[webloader ' + this.stime() + '] ',
			add = (typeof arguments[0] === 'string' ? 1 : 0)
			args = [prefix + (add ? arguments[0] : '')].concat(Array.prototype.slice.call(arguments, add));
		return console.log.apply(console, args);

		// for non-console logging
		// return this.somemethod(this.format.apply(this, args));
	}

	this.inspect = function(x, level) {
		if (level === undefined) level = 0;
		var ref = this, res = [], type = typeof x, padding = (new Array(level * 2 + 3)).join(' ');
		if (type === 'function') return ('' + x).split(')', 1)[0].strip().replace(/\s+/g, ' ') + ')';
		if (type === 'string') return '"' + x + '"';
		if (type !== 'object' || level > 1 || x === null) return '' + x;
		var prop = function(key) { return padding + key + ': ' + ref.inspect(x[key], level + 1); };
		if (x.hasOwnProperty('length'))
			for (var i = 0; i < x.length; i++) res.push(prop(i));
		else
			for (var k in x)
				if (x.hasOwnProperty(k)) res.push(prop(k));
		if (!res.length) return (x.hasOwnProperty('length') ? '[]' : '{}');
		return '\n' + res.join('\n');
	}

	// for non-console messages, something like this could be used in the same format as console.log
	// TODO: add proper %d, %f, %i, maybe %o
	this.format = function() {
		if (arguments.length < 2) return arguments[0];
		var args = arguments;
		return this.array(args[0].split('%s')).reduce(function(res, a, i) {
			// console.log('item ' + i + ': "' + a + '", args[' + i + ']: "' + args[i] + '", current result: "' + res + '"')
			return res + (i ? (args[i] === undefined ? '(?)' : args[i]) : '') + a;
		}, '');
	}

	this.is_true = function(x) { return x; }

	this.array = function(a) { return a.map && a.filter ? a : Array.prototype.slice.call(a); }

	this.test_regexp = function(file_pattern, expected) {
		var protocols = [
			'http://',
			'https://',
			'//'
		]
		var domains = [
			"localhost",
			"127.0.0.1",
			"some.domain.com"
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

		var generate = function(list, prefix) {
			return function (a) { return list.map(function(x) { return a + prefix + x; }); };
		}

		// paths get a '/' prefix; query params a '?'; etc

		var result = this.array(protocols).
			map(generate(domains, '')).flatten().
			map(generate(paths, '/')).flatten().
			map(generate(files, '')).flatten().
			map(generate(params, '?')).flatten().
			map(generate(hosts, '&server=')).flatten().
			map(generate(ports, '')).flatten();

		// return a specific item, if asked
		if (expected < 0) return [result[-expected]];

		var errors = result.filter(function(a) { return (a.match(file_pattern) || []).length !== expected; });

		// console.log(file_pattern)
		// console.log((result[0].match(file_pattern) || []).join('\n'))

		console.log('file pattern test: %s/%s errors%s', errors.length, result.length,
			(errors.length || '') && ', example: ' + errors[0] + '\n' + (errors[0].match(file_pattern) || []).join('\n'))
		return !errors;
	}

	var ref = this, init = function() { ref.init.apply(ref); };
	window.webloader ?
		window.setTimeout(init, 200) :
		document.addEventListener('DOMContentLoaded', init);

	return this;

}

return window.webloader = new WebLoader();

})(window);
