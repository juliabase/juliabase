all: main.js
.PHONY: clean all install

main.js: *.dart
	if [ "$$DEBUG" = "true" ];                                                                            \
	then                                                                                                  \
	    dart compile js -o main.js main.dart;                                                             \
	else                                                                                                  \
	    dart compile js --no-source-maps --minify -O3 --output main.js main.dart;                         \
	    rm main.js.*;                                                                                     \
	fi

install: main.js
	cp main.js ../jb_common/static/juliabase/js
	if [ "$$DEBUG" = "true" ];                                                                            \
	then                                                                                                  \
	    cp main.js.map ../jb_common/static/juliabase/js;                                                  \
	fi

clean:
	rm -Rf main.js main.js.*
