function LessWatch(window) {

	this.init = function() {
		this.files = $A(document.getElementsByTagName('link')).
			filter(function(a) { return a.href.slice(-5) === '.less'; }).
			map(function(a) { return a.href; })
		this.connect()
	}

	this.connect = function() {
		var url = "localhost:9000/less_updates";
		var socket = this.socket = new WebSocket("ws://" + url); 
		var ref = this, methods = ['onopen', 'onclose', 'onmessage']
		var wrapper = function(funcname) {
			this.parent.socket[funcname] = function() { ref[funcname].apply(ref, arguments); }
		}
		methods.each(wrapper, { parent: this })
	}

	this.log = function(message) {
		console.log(typeof message === 'string' ? 
			'[less-watch ' + (new Date()).toTimeString().slice(0, 8) + '] ' + message : 
			message
		);
	}

	this.onopen = function() {
		var files = this.files.map(function(a) { return a.replace(/https?:\/\/[\w\.-]+/, ''); });
		this.log('watching ' + files.join(', '));
		this.socket.send('watch\n' + files.join('\n'))
	}
	this.onclose = function() { this.log('disconnected by server!'); }

	this.onmessage = function(message) {
		// socket.send('initial message from client');
		// console.log(message)
		this.update(message.data);
	}

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

	this.parse = function(err, tree) {
		this.css = '';
		if (err) return this.log(err.message + ' (column ' + err.index + ')');
		this.css = tree.toCSS();
	}

	this.remove_existing = function(id) {
		id += ' {\n'
		var cut = function(target, from, to, parent) {
			var i = target.textContent.indexOf(from), 
				j = target.textContent.indexOf(to, i)
			// parent.log(('removing "' + from + '...' + to + '" from ' + target.id).replace(/\n/g, '|'))
			return target.textContent.slice(0, i) + target.textContent.slice(j)
		}
		var styles = $A(document.getElementsByTagName('style')).
			filter(function(a) { return a.textContent.indexOf('\n' + id) > -1 || a.textContent.slice(0, id.length) === id; }).
			each(function(a) { a.textContent = cut(a, id, "}\n", this.parent); }, { parent: this })
	}

	this.update = function(styles) {
		var css, id = (styles.slice(0, styles.indexOf('{')).strip());
		var thisref = this, parser = new less.Parser();

		this.remove_existing(id)
		this.log('updating ' + styles)
		parser.parse(styles, function(err, tree) { thisref.parse(err, tree); });

		if (!this.css) return;
		id = 'less-watch:' + id.replace(/ /g, '-')

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

	this.init()

}

watch = new LessWatch(window)
