#include <stdio.h>
#include <string.h>
#include <openssl/x509v3.h>
#include <openssl/x509.h>
#include <openssl/asn1.h>
#include <openssl/bio.h>
#include <openssl/obj_mac.h>
#include <openssl/err.h>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/pem.h>

int main(void) {
    OSSL_HASH *hash;
    OSSL_INFO_SYNTAX_POINTER *pointer;
    OSSL_INFO_SYNTAX *info;
    OSSL_PRIVILEGE_POLICY_ID *ppid;
    OSSL_ATTRIBUTE_DESCRIPTOR *ad;
    X509_ALGOR *alg;
    unsigned char *der = NULL;
    int derlen;
    X509_EXTENSION *ext;
    ASN1_OCTET_STRING *extval;
    X509_CRL *crl;
    X509_NAME *name;
    EVP_PKEY *pkey;
    unsigned char *crl_der = NULL;
    int crl_len;
    FILE *f;

    /* Build OSSL_HASH with hashValue deliberately left NULL (OPTIONAL, omitted) */
    hash = (OSSL_HASH *)OPENSSL_zalloc(sizeof(*hash));
    alg = X509_ALGOR_new();
    X509_ALGOR_set0(alg, OBJ_txt2obj("1.2.3.4.5", 1), V_ASN1_UNDEF, NULL);
    hash->algorithmIdentifier = alg;
    hash->hashValue = NULL; /* the omitted optional field */

    pointer = (OSSL_INFO_SYNTAX_POINTER *)OPENSSL_zalloc(sizeof(*pointer));
    pointer->name = sk_GENERAL_NAME_new_null();
    pointer->hash = hash;

    info = (OSSL_INFO_SYNTAX *)OPENSSL_zalloc(sizeof(*info));
    info->type = OSSL_INFO_SYNTAX_TYPE_POINTER;
    info->choice.pointer = pointer;

    ppid = (OSSL_PRIVILEGE_POLICY_ID *)OPENSSL_zalloc(sizeof(*ppid));
    ppid->privilegePolicy = OBJ_txt2obj("1.2.3.4.6", 1);
    ppid->privPolSyntax = info;

    ad = (OSSL_ATTRIBUTE_DESCRIPTOR *)OPENSSL_zalloc(sizeof(*ad));
    ad->identifier = OBJ_txt2obj("1.2.3.4.7", 1);
    ad->attributeSyntax = ASN1_OCTET_STRING_new();
    ASN1_STRING_set(ad->attributeSyntax, "syn", 3);
    ad->name = NULL;
    ad->description = NULL;
    ad->dominationRule = ppid;

    derlen = i2d_OSSL_ATTRIBUTE_DESCRIPTOR(ad, &der);
    if (derlen <= 0) { fprintf(stderr, "i2d failed\n"); return 2; }
    fprintf(stderr, "encoded %d bytes\n", derlen);

    extval = ASN1_OCTET_STRING_new();
    ASN1_OCTET_STRING_set(extval, der, derlen);
    OPENSSL_free(der);

    ext = X509_EXTENSION_create_by_NID(NULL, NID_attribute_descriptor, 0, extval);
    if (ext == NULL) { fprintf(stderr, "ext create failed\n"); ERR_print_errors_fp(stderr); return 3; }

    /* Now build a minimal, properly-signed X509_CRL carrying this extension */
    crl = X509_CRL_new();
    X509_CRL_set_version(crl, 1); /* v2 */

    name = X509_NAME_new();
    X509_NAME_add_entry_by_txt(name, "CN", MBSTRING_ASC, (unsigned char *)"test", -1, -1, 0);
    X509_CRL_set_issuer_name(crl, name);
    X509_NAME_free(name);

    X509_CRL_set1_lastUpdate(crl, ASN1_TIME_set(NULL, 0));
    X509_CRL_set1_nextUpdate(crl, ASN1_TIME_set(NULL, 1000000));

    X509_CRL_add_ext(crl, ext, -1);
    X509_EXTENSION_free(ext);
    ASN1_OCTET_STRING_free(extval);
    OSSL_ATTRIBUTE_DESCRIPTOR_free(ad);

    pkey = EVP_RSA_gen(512);
    if (pkey == NULL) { fprintf(stderr, "keygen failed\n"); ERR_print_errors_fp(stderr); return 4; }

    if (X509_CRL_sign(crl, pkey, EVP_sha256()) <= 0) {
        fprintf(stderr, "sign failed\n");
        ERR_print_errors_fp(stderr);
        return 5;
    }

    crl_len = i2d_X509_CRL(crl, &crl_der);
    if (crl_len <= 0) { fprintf(stderr, "crl i2d failed\n"); return 6; }
    fprintf(stderr, "crl encoded %d bytes\n", crl_len);

    f = fopen("/tmp/crl.der", "wb");
    fwrite(crl_der, 1, crl_len, f);
    fclose(f);

    OPENSSL_free(crl_der);
    X509_CRL_free(crl);
    EVP_PKEY_free(pkey);

    fprintf(stderr, "wrote /tmp/crl.der\n");
    return 0;
}
