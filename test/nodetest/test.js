var MAX7219 = require('max7219');
var async = require('async');

var switchtime = 3000
var switchtime_min = 500
var disp = new MAX7219("/dev/spidev0.0");

disp.setDecodeNone();
disp.setDisplayIntensity(15);
disp.setScanLimit(8);

array = [0,0,0,0,0,0,0,0];

// function enable(){
// 	disp.startup(function(){

// 	});
// 	disp.setDisplayIntensity(15);
// 	async.eachSeries([0,1,2],function(i,callback){
// 		async.eachSeries([0,1,2,3,4,5,6,7], function(j,callback){
// 			var arrbk = array.slice();
// 			arrbk[j]=1;
// 			// console.log(j,i,arrbk)
// 			disp.setDigitSegments(i, arrbk);
// 			setTimeout(callback,switchtime_min);
// 		},callback)
// 	}, function(){
// 		setTimeout(disable,switchtime);
// 	})

	
// }

// function disable(){
// 	disp.shutdown();
// 	setTimeout(enable,switchtime);
// }
// enable();

disp.setDisplayIntensity(15);
disp.setDecodeAll();
disp.setDigitSymbol(0, "8");
disp.setDigitSymbol(1, "8");
disp.setDigitSymbol(2, "8");

// disp.clearDisplay();
// disp.startDisplayTest();
