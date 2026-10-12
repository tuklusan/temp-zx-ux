/* t1_lex.c - C48 conformance: source form, comments, identifiers, tokens
 * and literals (spec sections 4-17).  Every check is ck(id, condition) with
 * the governing paragraph numbers in the comment after it.
 */
#include "ck.h"

/* identifiers: case-sensitive, 15 visible characters, leading underscore,
 * and spellings other languages reserve but C48 does not */
int abc;
int Abc;
int ABC;
int abc123;
int _abc;
int abc_DEF;
int abcdefghijklmno;
int abcdefghijklmnO;
int bool;
int true;
int false;
int nullptr;
int alignas;
int typeof;
int NaN;
int Inf;
int Infinity;

char *same_literal(void)
{
    return "xyz";
}

int main(void)
{
	int i;
	int j;
	int k;
	char *s;
	char *t;
	float f;

	/* 4: a TAB-indented, printable-ASCII, LF-terminated source */
	ck(1001, 1);                                    /* P0039 P0040 P0041 P0042 P0043 P0047 P1039 */

	/* 6, 7: white space and comments */
	k = 1/**/+/**/2;
	ck(1101, k == 3);                               /* P0063 P0064 P0066 P0067 P0079 */
	k = 0; /* a block comment
	          spanning lines */ k = k + 1;
	ck(1102, k == 1);                               /* P0071 P0075 P0070 */
	k = 0; // a line comment ends at the LF
	k = k + 2;
	ck(1103, k == 2);                               /* P0073 P0074 P0072 */
	k = 0; /* /* not nested: the first close ends it */ k = 7;
	ck(1104, k == 7);                               /* P0076 */
	s = "/* // */";
	ck(1105, sizeof("/* // */") == 9 && s[0] == '/' && s[1] == '*' && s[3] == '/'); /* P0078 */
	k = '/';
	ck(1106, k == 47);                              /* P0078 */
	k = 5;
	k = + +k;
	ck(1107, k == 5);                               /* P0130 P0066 */
	i = 1;
	j = 2;
	k = i+++j;
	ck(1108, k == 3 && i == 2 && j == 2);           /* P0120 */
	k = i - -j;
	ck(1109, k == 4);                               /* P0130 P0066 */

	/* 8: identifiers */
	abc = 1;
	Abc = 2;
	ABC = 3;
	ck(1201, abc == 1 && Abc == 2 && ABC == 3);     /* P0082 P0083 P0084 P0094 P0095 P0096 P1007 */
	abcdefghijklmno = 4;
	abcdefghijklmnO = 5;
	ck(1202, abcdefghijklmno == 4 && abcdefghijklmnO == 5); /* P0085 P0086 P0089 P0090 P0091 P0092 P0093 P1007 */
	abc123 = 6;
	_abc = 7;
	abc_DEF = 8;
	ck(1203, abc123 + _abc + abc_DEF == 21);        /* P0083 P0116 P1038 */
	bool = 1;
	true = 2;
	false = 3;
	nullptr = 4;
	alignas = 5;
	typeof = 6;
	NaN = 7;
	Inf = 8;
	Infinity = 9;
	ck(1204, bool + true + false + nullptr + alignas + typeof == 21); /* P0115 P0101 */
	ck(1205, NaN + Inf + Infinity == 24);           /* P0189 P0115 P0208 */

	/* 12, 13: integer literals and their types */
	ck(1301, 0 == 0 && 123 == 100 + 23);            /* P0135 P0137 P0142 P0136 P0141 P0158 P1039 */
	ck(1302, 077 == 63 && 00 == 0 && 0x2a == 42 && 0X2A == 42 && 0xff == 255); /* P0135 P0137 P0142 */
	ck(1303, 65535u == 0xFFFFu && 0XFFU == 255 && 0XABCDU == 43981u); /* P0138 P0142 P0831 */
	ck(1304, (32767 > -1) == 1);                    /* P0150 P0151 */
	ck(1305, (32768 > -1) == 0);                    /* P0150 P0152 P0156 */
	ck(1306, (0x8000 > -1) == 0 && (0100000 > -1) == 0); /* P0152 P0156 */
	ck(1307, (0x7fff > -1) == 1 && (077777 > -1) == 1); /* P0151 P0156 */
	ck(1308, (1u > -1) == 0 && (0x1U > -1) == 0 && (01u > -1) == 0); /* P0153 P0154 P0155 P0156 */
	ck(1309, 65535 == 65535u && (65535 > -1) == 0); /* P0145 P0152 P0158 */
	ck(1310, -32768 == 32768u && -32768 > 0);       /* P0140 P0146 P0845 P1049 */
	ck(1311, (int)0x8000u < 0 && (-32767 - 1) < 0 && (int)0x8000u == (-32767 - 1)); /* P0146 P0845 P1049 */
	ck(1312, -1 == 0 - 1 && - 1 == -1);             /* P0140 */
	ck(1313, sizeof(32767) == 2 && sizeof(65535u) == 2); /* P0149 P0157 */

	/* 14: character literals */
	ck(1401, 'A' == 65 && '0' == 48 && '\n' == 10 && '\x7f' == 127); /* P0161 P0163 P0162 P0831 */
	ck(1402, sizeof('A') == 2 && '\xff' == 255 && ('\xff' > 0) == 1); /* P0161 */
	ck(1403, '\\' == 0x5C && '\'' == 0x27 && '\"' == 0x22 && '\0' == 0); /* P0164 P0165 */
	ck(1404, '\a' == 7 && '\b' == 8 && '\t' == 9 && '\n' == 10); /* P0164 P0165 */
	ck(1405, '\v' == 11 && '\f' == 12 && '\r' == 13); /* P0164 P0165 */
	ck(1406, '\x00' == 0 && '\x41' == 'A' && '\xff' == 255 && '\xAb' == 171); /* P0166 P0167 */
	ck(1407, '"' == 34);                            /* P0161 */

	/* 15: string literals */
	s = "hello\n";
	ck(1501, sizeof("hello\n") == 7 && s[5] == 10 && s[6] == 0); /* P0175 P0176 P0177 P0831 */
	s = "\\\'\"\0\a\b\t\n\v\f\r";
	ck(1502, sizeof("\\\'\"\0\a\b\t\n\v\f\r") == 12); /* P0164 P0175 */
	ck(1503, s[0] == 0x5C && s[1] == 0x27 && s[2] == 0x22 && s[3] == 0 && s[4] == 7 && s[5] == 8); /* P0164 P0165 P0175 */
	ck(1504, s[6] == 9 && s[7] == 10 && s[8] == 11 && s[9] == 12 && s[10] == 13 && s[11] == 0); /* P0164 P0165 P0175 */
	s = "\x041";
	ck(1505, sizeof("\x041") == 3 && s[0] == 4 && s[1] == '1'); /* P0166 P0168 */
	s = "hello " "world";
	t = "hello world";
	ck(1506, sizeof("hello " "world") == 12 && s[5] == ' ' && s[6] == 'w' && s[11] == 0); /* P0178 */
	i = 0;
	while (s[i] != 0 && s[i] == t[i])
		i++;
	ck(1507, i == 11 && t[11] == 0);                /* P0178 */
	ck(1508, sizeof("a" /* c */ "b" // c
	                "c") == 4);                     /* P0178 */
	ck(1509, sizeof("") == 1 && sizeof("abc") == 4); /* P0177 P0832 */
	s = "same";
	t = "same";
	ck(1510, s != t);                               /* P0181 */
	ck(1511, same_literal() == same_literal());     /* P0181 */
	s = "\xff";
	ck(1512, s[0] == 255 && s[0] > 128);            /* P0050 P0166 P0216 */

	/* 16: floating literals */
	f = 1.;
	ck(1601, f == 1.0 && .5 * 2.0 == 1.0);          /* P0185 P0186 P0187 P0831 */
	ck(1602, 1e3 == 1000.0 && 1E-2 > .0099 && 1E-2 < .0101 && .25e+1 > 2.49 && .25e+1 < 2.51); /* P0186 P0187 */
	ck(1603, 1.25f == 1.25 && 1.25F == 1.25 && 2e0f == 2.0); /* P0186 P0188 */
	ck(1604, 0.0 == 0 && sizeof(1.5) == 5 && sizeof(1.25f) == 5); /* P0188 P0194 */
	f = -1.5;
	ck(1605, f < 0.0 && -f == 1.5);                 /* P0190 */
	ck(1606, 1.e2 == 100.0 && 12E1 == 120.0 && 3.5e-1 > .349 && 3.5e-1 < .351); /* P0186 */

	/* 11: every supported operator and punctuator in one place */
	i = 6;
	j = 3;
	k = (i + j) * (i - j) / j % 5;          /* + - * / % ( ) */
	ck(1701, k == 4);                               /* P0121 P0122 P0123 P0124 P0833 P0997 P0998 */
	k = (i << 1) + (i >> 1) + (i & j) + (i | j) + (i ^ j) + ~i; /* << >> & | ^ ~ */
	ck(1702, k == 12 + 3 + 2 + 7 + 5 - 7);          /* P0121 P0122 P0833 */
	k = (i < j) + (i <= j) + (i > j) + (i >= j) + (i == j) + (i != j) + !i; /* relational, ! */
	ck(1703, k == 3);                               /* P0121 P0122 P0833 */
	k = (i && j) + (i || 0);
	i++;
	j--;
	++i;
	--j;
	ck(1704, k == 2 && i == 8 && j == 1);           /* P0121 P0122 P0833 */
	{
		int arr[2];                             /* [ ] { } ; , */
		arr[0] = 1;
		arr[1] = 2;
	}
	ck(1705, 1);                                    /* P0124 P0125 P0999 P1000 */

	return ck_done();
}
