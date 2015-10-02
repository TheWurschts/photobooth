#include <algorithm>

using namespace std;

extern "C" void greenbox(int* buffer, int w, int h) {
    for (int x = 0; x != w; ++x) {
        for (int y = 0; y != h; ++y) {
            int& pixel = buffer[x + y * w];
            unsigned char* rgb = (unsigned char*) &pixel;
            if (rgb[1] > 50) {
                if ((rgb[1] * .9) > rgb[0] && (rgb[1] * .9) > rgb[2]) {
                    rgb[3] = 0;
                }
            } else {
                if ((rgb[1] * .6) > rgb[0] && (rgb[1] * .6) > rgb[2]) {
                    rgb[3] = 0;
                }
            }
        }
    }
}

extern "C" void sepia(int* buffer, int w, int h) {
    for (int x = 0; x != w; ++x) {
        for (int y = 0; y != h; ++y) {
            int& pixel = buffer[x + y * w];
            unsigned char* rgb = (unsigned char*) &pixel;
            rgb[2] = (unsigned char) min(255., rgb[2] * .393 + rgb[1] * .769 + rgb[0] * .189);
            rgb[1] = (unsigned char) min(255., rgb[2] * .349 + rgb[1] * .686 + rgb[0] * .168);
            rgb[0] = (unsigned char) min(255., rgb[2] * .272 + rgb[1] * .534 + rgb[0] * .131);
        }
    }
}

extern "C" void scale(int* srcbuf, int srcw, int srch, int* dstbuf, int dstw, int dsth) {
     int x_ratio = (int) ((srcw << 16) / dstw) + 1;
     int y_ratio = (int) ((srch << 16) / dsth) + 1;
     int x, y;
     for (int i = 0; i != dsth; ++i) {
        for (int j = 0; j != dstw; ++j) {
            x = ((j * x_ratio) >> 16);
            y = ((i * y_ratio) >> 16);
            dstbuf[i * dstw + j] = srcbuf[y * srcw + x];
        }
     }
}
