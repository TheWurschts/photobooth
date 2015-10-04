var MAX7219 = require('max7219');

var disp = new MAX7219("/dev/spidev0.0");
disp.setDecodeNone();
disp.setScanLimit(3);
disp.startup();
disp.setDigitSegments(0, [1, 0, 1, 1, 0, 1, 1, 1]);
disp.setDigitSegments(1, [0, 1, 0, 0, 1, 1, 1, 1]);
disp.setDigitSegments(2, [1, 0, 0, 0, 1, 1, 1, 0]);