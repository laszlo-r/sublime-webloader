function LessWatch(window) {

	this.connect = function() {
		var url = "localhost:9000/less_updates";
		var socket = this.socket = new WebSocket("ws://" + url); 
		var thisref = this;
		this.socket.onopen = this.onopen;
		this.socket.onclose = this.onclose;
		this.socket.onmessage = function(message) { thisref.onmessage.apply(thisref, [message]); }
	}

	this.onopen = function() { console.log('socket opened'); }
	this.onclose = function() { console.log('socket closed'); }

	this.onmessage = function(message) {
		// socket.send('initial message from client');
		// console.log(message.data);
		// console.log(this)
		this.update(message.data);
	}

	// http://werxltd.com/wp/2010/05/13/javascript-implementation-of-javas-string-hashcode-method/
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
		if (err) return console.log('[less-watch] ' + err.message + ' (column ' + err.index + ')');
		this.css = tree.toCSS();
	}

	this.update = function(styles) {
		var css, id = 'less:' + (styles.slice(0, styles.indexOf('{')).strip());
		var thisref = this, parser = new less.Parser();

		parser.parse(styles, function(err, tree) { thisref.parse(err, tree); });

		if (!this.css) return;
		console.log('updating "' + id + '"')
		// console.log('with: ' + this.css);

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

	this.connect()

}

watch = new LessWatch(window)
