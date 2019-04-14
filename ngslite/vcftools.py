import subprocess
from functools import partial
printf = partial(print, flush=True)


def __call(cmd):
    printf('CMD: ' + cmd)
    try:
        subprocess.check_call(cmd, shell=True)
    except Exception as inst:
        printf(inst)


def bcftools_variant_call(ref, bam, output=None):
    """
    Wrapper function of "bcftools mpileup" -> BCF (genotype likelihood) -> "bcftools call" -> BCF (variants)
    BCF stands for binary VCF file

    Args:
        ref: str, path-like
            The reference fasta file

        bam: str, path-like
            The alignment BAM file

        output: str, path-like
            The output BCF file
    """
    # -Ou: output uncompressed bcf
    # -m: use the default calling method
    # -v: output only variant sites
    # -o <file_out>
    # -f <ref_fasta>
    if output is None:
        output = bam[:-4] + '.bcf'
    __call(f"bcftools mpileup -Ou -f {ref} {bam} | bcftools call -Ou -m -v -o {output}")


def sort_bcf(file, keep=False):
    """
    Wrapper function of "bcftools sort" to sort BCF and outputs a BCF file.

    Args:
        file: str, path-like

        keep: bool
            Keep the input file or not
    """
    file_out = f"{file[:-4]}_sorted.{file[-3:]}"
    # -Ou: output uncompressed bcf
    # -o <file_out>
    __call(f"bcftools sort -Ou -o {file_out} {file}")
    if not keep:
        __call(f"rm {file}")
        __call(f"mv {file_out} {file}")


def subset_bcf_regions(file, regions, output=None, keep=True):
    """
    Args:
        file: str, path-like
            The input BCF file

        regions: list of str
            Each str is a region of the reference genome, e.g.
                chr1            chromosome 1
                chr3:1000-2000  chromosome 3 from 1000th (inclusive) to 2000th (inclusive) base

        output: str, path-like
            The output BCF file
            If None, add subscript '_subset' to the input <file>

        keep: bool
            If False, delete the input <file> and rename the output as the input <file>
            Overrides the <output> file name
    """
    # Convert regions list into a string
    # ['chr1', 'chr2:1001-2000'] -> ' chr1,chr2:1001-2000'
    regions = ' ' + ','.join(regions)  # comma-separated regions

    if output is None:
        output = file[:-4] + '_subset.bcf'

    # -Ou: output uncompressed bcf
    # -o <file_out>
    __call(f"bcftools view -Ou -o {output} {file}{regions}")

    if not keep:
        __call(f"rm {file}")
        __call(f"mv {output} {file}")


class VcfParser:
    """
    A VCF file parser for VCFv4.3
    """
    def __init__(self, file):
        """
        The header section is parsed upon instantiation.

        Args:
            file: str, path-like object
        """
        self.__vcf = open(file, 'r')
        header = ''
        while True:
            # Get the current position
            pos = self.__vcf.tell()
            # Readline and move on to the next position
            line = self.__vcf.readline()
            if line.startswith('#'):
                header = header + line
            else:
                # If reaching the alignment section, that is,
                #   the header section has been parsed completely,
                #   then go back one line and break out the loop
                self.__vcf.seek(pos)
                break
        # Store the header string
        self.__header = header

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return

    def __iter__(self):
        return self

    def __next__(self):
        r = self.next()
        if r:
            return r
        else:  # r is None
            self.__vcf.close()
            raise StopIteration

    def next(self):
        """
        Each line of the SAM file has at least 11 fields

        #   Col	Field   Type    Description
        0   1   CHROM   String  The name of the sequence (typically a chromosome)
        1   2   POS     Int     The 1-based position of the variation on the given sequence
        2   3   ID      String  The identifier of the variation
        3   4   REF     String  The reference base (or bases in the case of an indel) at the given position on the given reference sequence
        4   5   ALT     String  The list (separated by ,) of alternative alleles at this position
        5   6   QUAL    Int     A quality score associated with the inference of the given alleles.
        6   7   FILTER  String  A flag indicating which of a given set of filters the variation has passed
        7   8   INFO    String  An extensible list of key-value pairs (fields) describing the variation, for example, NS=2;DP=10;AF=0.333,0.667;AA=T;DB
        8   9                   Optional fields...

        Returns: tuple of str or int
            The length of tuple might be > 8,
              depending of the presence of additional optional fields
        """
        line = self.__vcf.readline().rstrip()
        if line:
            fields = line.split('\t')
            for i in (1, 5):
                fields[i] = int(fields[i])
            return tuple(fields)
        else:  # line == ''
            return None

    def get_header(self):
        """Returns the header section (str) of VCF file"""
        return self.__header

    def close(self):
        self.__vcf.close()


class VcfWriter:
    def __init__(self, file, header, mode='w'):
        """
        The header section should be written in upon instantiation.

        Args:
            file: str, path-like object

            header: str
                The header section

            mode: str, 'w' or 'a'
        """
        self.__sam = open(file, mode)
        if not header == '':
            self.__sam.write(header.rstrip() + '\n')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return

    def write(self, alignment):
        """
        Args:
            alignment: tuple of str or int
                Containing 11 (at least) fields of a line of SAM file
        """
        self.__sam.write('\t'.join(map(str, alignment)) + '\n')

    def close(self):
        self.__sam.close()


def print_vcf(var=None):
    """
    Pretty print a variant (tuple) from vcf file

    Args:
        var: tuple or list of str or int
            Containing (at least) 8 fields of a variant from vcf file
    """
    if var is None:
        text = """\
#   Col	Field   Type    Description
0   1   CHROM   String  The name of the sequence (typically a chromosome)
1   2   POS     Int     The 1-based position of the variation on the given sequence
2   3   ID      String  The identifier of the variation
3   4   REF     String  The reference base (or bases in the case of an indel) at the given position on the given reference sequence
4   5   ALT     String  The list (separated by ,) of alternative alleles at this position
5   6   QUAL    Int     A quality score associated with the inference of the given alleles.
6   7   FILTER  String  A flag indicating which of a given set of filters the variation has passed
7   8   INFO    String  An extensible list of key-value pairs (fields) describing the variation, for example, NS=2;DP=10;AF=0.333,0.667;AA=T;DB
8   9                   Optional fields..."""
        printf(text)

    elif type(var) is tuple or type(var) is list:
        fields = ['CHROM ', 'POS   ', 'ID    ', 'REF   ', 'ALT   ',
                  'QUAL  ', 'FILTER', 'INFO  ']
        for i in range(8):
            printf(f"{i}\t{fields[i]}\t{var[i]}")
        if len(var) > 8:
            for i in range(8, len(var)):
                printf(f"{i}\t     \t{var[i]}")


def unpack_vcf_info(var):
    """
    Args:
        var: tuple or list of str or int
            Containing (at least) 8 fields of a variant from vcf file

    Return: dict
        Key, value pairs from the INFO (column 7) of a variant
        Values still str, not converted to int or float
    """
    func = lambda x: x.split('=')
    return {key: val for key, val in map(func, var[7].split(';'))}

