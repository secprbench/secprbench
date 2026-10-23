#ifndef STUB_LIBRTMP_RTMP_H
#define STUB_LIBRTMP_RTMP_H
/* Minimal stand-in for librtmp's public API: only the container has no
 * librtmp -dev headers (just the runtime .so.1), so we supply our own
 * declarations plus matching RTMP_* implementations in the harness. */

typedef struct RTMPSockBuf {
  int sb_socket;
} RTMPSockBuf;

typedef struct RTMP_READ {
  int status;
} RTMP_READ;

typedef struct RTMP_LNK {
  int protocol;
  int lFlags;
} RTMP_LNK;

#define RTMP_READ_COMPLETE   1
#define RTMP_READ_EOF        2
#define RTMP_FEATURE_WRITE   0x01
#define RTMP_FEATURE_HTTP    0x02
#define RTMP_LF_LIVE         0x01
#define RTMP_LF_BUFX         0x02

typedef struct RTMP {
  RTMPSockBuf m_sb;
  RTMP_READ   m_read;
  RTMP_LNK    Link;
  int         m_bSendCounter;
} RTMP;

#define RTMP_LIB_VERSION 0x020400

RTMP *RTMP_Alloc(void);
void RTMP_Init(RTMP *r);
void RTMP_SetBufferMS(RTMP *r, int ms);
int RTMP_SetupURL(RTMP *r, char *url);
void RTMP_Close(RTMP *r);
void RTMP_Free(RTMP *r);
int RTMP_Connect1(RTMP *r, void *unused);
int RTMP_ConnectStream(RTMP *r, int seek);
int RTMP_Read(RTMP *r, char *buf, int size);
int RTMP_Write(RTMP *r, const char *buf, int size);

#endif
