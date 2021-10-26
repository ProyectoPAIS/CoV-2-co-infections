#!/usr/bin/env python3

import os
import sys
import json
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import Bio.SeqIO as bpio
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq

from itertools import groupby


def e(cmd):
    if os.environ.get("verbose"):
        print(cmd)
    sp.run(cmd, shell=True)


def merge_vcfs(args):
    outfolder = os.path.dirname(args.output)
    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    if not os.path.exists(outfolder):
        sys.stderr.write(f"'{outfolder}' could not be created")
        sys.exit(1)
    if not os.path.exists(args.reference):
        sys.stderr.write(f"'{args.reference}' does not exists")
        sys.exit(1)
    vcf_files = []
    for x in glob(args.vcfs_dir + "/*vcf*"):
        if x.endswith(".vcf") or x.endswith(".vcf.gz") or x.endswith(".gvcf") or x.endswith(".gvcf.gz"):
            vcf_files.append(x)
    if not vcf_files:
        raise FileNotFoundError(f'no .vcf or .vcf.gz files where found at {args.vcfs_dir}')
    vcfs = " ".join([f"--variant {x}" for x in vcf_files])
    # docker run -u $(id -u ${{USER}}):$(id -g ${{USER}})  -v $PWD:/out -w /out broadinstitute/gatk:4.2.2.0 \
    cmdx = f"""/gatk/gatk CombineGVCFs -R {args.reference} {vcfs} -O {args.output}.raw"""
    e(cmdx)
    # docker run -u $(id -u ${{USER}}):$(id -g ${{USER}})  -v $PWD:/out -w /out broadinstitute/gatk:4.2.2.0 \
    cmdx = f"""/gatk/gatk GenotypeGVCFs \
                    -R "{args.reference}" -ploidy 2 \
                    -V "{args.output}.raw" \
                    -O "{args.output}" 
        """
    e(cmdx)


def download(args):
    outfolder = args.output_folder
    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    if not os.path.exists(outfolder):
        sys.stderr.write(f"'{outfolder}' could not be created")
        sys.exit(1)
    cmdx = f'wget -O {outfolder}/MN996528.fna "https://www.ncbi.nlm.nih.gov/sviewer/viewer.cgi?tool=portal&save=file&log$=seqview&db=nuccore&report=fasta&id=1802633808&conwithfeat=on&withparts=on&hide-cdd=on"'
    sp.run(cmdx, shell=True)
    # docker run -u $(id -u ${{USER}}):$(id -g ${{USER}}) -v $DIND:/out -w /out staphb/samtools \
    cmdx = f"""samtools dict -o {outfolder}/MN996528.dict {outfolder}/MN996528.fna"""
    # makeblastdb -dbtype nucl -in /ref/MN996528.fna && bwa index MN996528.fna && samtools faidx MN996528.fna
    e(cmdx)
    # docker run -u $(id -u ${{USER}}):$(id -g ${{USER}}) -v $DIND:/out -w /out staphb/samtools \
    cmdx = f"""samtools faidx {outfolder}/MN996528.fna"""
    e(cmdx)


def variant_filter(args):
    """MN996528.1	1879	.	A	G	14552.79	.	AC=2;AF=5.556e-03;AN=360;BaseQRankSum=2.16;DP=113297;ExcessHet=0.0061;FS=0.838;InbreedingCoeff=0.8880;MLEAC=2;MLEAF=5.556e-03;MQ=59.99;MQRankSum=0.00;QD=28.76;ReadPosRankSum=1.03;SOR=0.597	GT:AD:DP:GQ:PGT:PID:PL:PS	0/0:717,0:717:99:.:.:0,120,1800	0/0:166,0:166:99:.:.:0,120,1800	0/0:395,0:395:99:.:.:0,120,1800	0/0:354,0:354:99:.:.:0,120,1800	0/0:464,0:464:99:.:.:0,120,1800	0/0:363,0:363:99:.:.:0,120,1800	0/0:464,0:464:99:.:.:0,120,1800	0/0:396,0:396:99:.:.:0,120,1800	0/0:288,0:288:99:.:.:0,120,1800	0/0:371,0:371:99:.:.:0,120,1800	0/0:347,0:347:99:.:.:0,120,1800	0/0:422,0:422:99:.:.:0,120,1800	0/0:517,0:517:99:.:.:0,120,1800	0/0:392,0:392:99:.:.:0,120,1800	0/0:392,0:392:99:.:.:0,120,1800	0/0:465,0:465:99:.:.:0,120,1800
        """
    if not os.path.exists(args.vcf):
        sys.stderr.write(f"'{args.vcf}' does not exists\n")
        sys.exit(1)

    print(f"Running lowfreq variant detection with:")
    print(f'- Minimun allele read depth: {args.min_allele_depth}')
    print(f'- max %N to discard a position: {args.min_coverage}')
    print(f'- minimun minority variant frequency: {args.min_freq}')

    print("----------------")
    h = gzip.open(args.vcf, "rt") if args.vcf.endswith(".gz") else open(args.vcf)
    number_of_variable_sites = 0
    number_of_mutations = 0
    try:
        samples = None
        variants = {}
        for line in h:
            if line.startswith("#CHROM"):
                samples = line.split()[9:]
            elif not line.startswith("#"):
                number_of_variable_sites += 1

                vec = line.split()
                pos = int(vec[1])
                ref = vec[3]
                alts = {i: x for i, x in enumerate(vec[4].split(","))}
                number_of_mutations += len(set(vec[4].split(",")) - set(["*", "N"]))

                gt_options = {k + 1: v for k, v in alts.items()}
                gt_options[0] = ref
                gt_options[99] = "N"
                format_f = vec[8]  # GT:AD:DP:GQ:PGT:PID:PL:PS
                gt_index = [i for i, x in enumerate(format_f.split(":")) if x == "GT"]
                if not gt_index:
                    sys.stderr.write("not all pos/samples have a GT field")
                    sys.exit(2)
                gt_index = gt_index[0]
                ad_index = [i for i, x in enumerate(format_f.split(":")) if x == "AD"]
                if not ad_index:
                    sys.stderr.write("not all pos/samples have a AD field")
                    sys.exit(2)
                dp_index = [i for i, x in enumerate(format_f.split(":")) if x == "DP"]
                if not dp_index:
                    sys.stderr.write("not all pos/samples have a GT field")
                    sys.exit(2)

                ad_index = ad_index[0]
                dp_index = dp_index[0]
                low_freq = False
                pos_data = {}
                for idx, sample in enumerate(samples):
                    gt = vec[9 + idx].split(":")[gt_index]
                    dp = int(vec[9 + idx].split(":")[dp_index])

                    ad = vec[9 + idx].split(":")[ad_index]

                    ads = [int(x) for x in ad.split(",") if x != "."]
                    if ads:
                        min_ad = min(ads)
                        gt_vec = [int(x) if x != "." else 99 for x in gt.replace("|", "/").split("/")]
                        pos_data[sample] = [{gt_options[gt_num]:
                                                 ([int(x) for x in ad.split(",")[gt_num]] if gt_num != 99 and (
                                                         min_ad > args.min_allele_depth) else "?")
                                             for gt_num in gt_vec},
                                            {gt_options[i]: int(ad_num) for i, ad_num in enumerate(ad.split(","))}]

                        if ads and min_ad > args.min_allele_depth and len(set(gt.replace("|", "/").split("/"))) > 1:
                            low_freq = True
                if low_freq:
                    variants[pos] = pos_data

    finally:
        h.close()
    variants = dict(variants)

    print(f'number of variable sites: {number_of_variable_sites}')
    print(f'number of mutations: {number_of_mutations}')

    excluded_positions = []
    low_freq_freq = []
    high_freq_freq = []
    # low_freq_pos = []
    low_freq_muts = []
    entries_data = {}

    for pos, samples_variants in variants.items():
        ns = 0
        for sample, (gts, ads) in samples_variants.items():
            is_n = (1 if "N" in gts else 0)
            ns += is_n

        if (1 - (1.0 * ns / len(samples))) < args.min_coverage:
            excluded_positions.append(pos)
            #     if not is_n:
            #         low_freq_muts.append(low_freq_mut)
            #         low_freq_freq += min_freqs
            #         high_freq_freq += consensus_freqs
            # else:

    print(f'excluded positions( Ns count greater than threashold):{len(excluded_positions)}')
    discarded_low_depth = defaultdict(list)
    variant_samples = defaultdict(list)
    for pos, samples_variants in variants.items():
        variant_samples_pos = defaultdict(list)
        if pos not in excluded_positions:
            min_freqs = []
            consensus_freqs = []
            entries = {}
            valid_min_variant = False
            for sample, (gts, ads) in samples_variants.items():
                if len(gts) > 1:
                    depth = sum(ads.values())
                    freqs = [(k, 1 * v / depth) for k, v in sorted(ads.items(), key=lambda x: x[1])]
                    min_variant = freqs[0]
                    dp = sum(ads.values())
                    if min_variant[1] >= args.min_freq:
                        if (dp > args.min_allele_depth):
                            min_freqs.append(min_variant[1])
                            consensus_variant = freqs[-1]
                            consensus_freqs.append(min_variant[1])
                            low_freq_mut = [pos, min_freqs]
                            variant_samples_pos[f'{pos}_{min_variant[0]}'].append(sample)
                            valid_min_variant = True
                            low_freq_freq.append(freqs[0][1])
                            high_freq_freq.append(freqs[-1][1])
                        else:
                            discarded_low_depth[sample].append([pos, ads])
                    else:
                        consensus_variant = list(gts.items())[0][0]
                        min_variant = [""]
                        high_freq_freq.append(freqs[-1][1])
                else:
                    consensus_variant = list(gts.items())[0][0]
                    min_variant = [""]
                entries[sample] = [consensus_variant, min_variant, gts, ads]
            if valid_min_variant:
                entries_data[pos] = entries
                for k, v in variant_samples_pos.items():
                    variant_samples[k] = v

    print(f'low freq positions:{len(entries_data)}')
    print(f'low freq mutations:{len(variant_samples)}')

    variant_samples = dict(variant_samples)
    entries_data = dict(entries_data)

    with open(f"{args.out}", "w") as h:
        data = {"variant_samples": variant_samples, "entries_data": entries_data,
                "discarded_low_depth": discarded_low_depth,
                "excluded_positions": excluded_positions, "low_freq_freq": low_freq_freq,
                "high_freq_freq": high_freq_freq}
        json.dump(data, h)


def aln(h, output, refseq=None, included_samples=None):
    # if hasattr(vcf_file, "read"):
    #     h = vcf_file
    # else:
    #     h = open(vcf_file)
    try:
        base_idx = 0
        for line in h:
            if line.startswith("#"):
                if line.startswith("#CHROM"):
                    samples = [x.strip() for x in line.split()[9:]]

                    seqmap = {s: "" for s in samples}
                continue
            break

        for line in h:
            _, pos, _, ref, alts = line.split()[:5]
            pos = int(pos)
            alts = [ref] + alts.split(",")
            gts = [x[0] for x in line.split()[9:]]
            gts = ["N" if x[0] == "." else alts[int(x[0])] for x in gts]
            pos_size = max([len(x) for x in alts])
            for i, s in enumerate(samples):
                if not included_samples or s in included_samples:
                    subseq = refseq[base_idx:pos] + gts[i].ljust(pos_size, "-")
                    seqmap[s] += subseq

            sizes = {}
            for s in samples:
                if not included_samples or s in included_samples:
                    sizes[s] = len(seqmap[s])
            assert len(set(sizes.values())) == 1, [base_idx, set(sizes.values()),
                                                   json.dumps({k: [x[0] for x in v] for k, v in
                                                               groupby(sorted(sizes.items(), key=lambda x: x[1]),
                                                                       lambda x: x[1])})]

            base_idx = pos + len(ref)
    finally:
        h.close()

    for s in samples:
        if not samples or s in included_samples:
            seqmap[s] += refseq[base_idx:]

    if hasattr(output, "write"):
        h = output
    else:
        h = open(output, "w")
    try:
        for k, v in seqmap.items():
            bpio.write(SeqRecord(id=k, name="", description="", seq=Seq(v)), h, "fasta")
    finally:
        h.close()


def comparative_analysis(json_file, output_dir,deviation_lowfreq=2, min_lowfreq=None):
    assert os.path.exists(json_file), f'"{json_file}" does not exists'
    with open(json_file) as h:
        data = json.load(h)

    min_per_sample = defaultdict(list)
    pos_data = {}
    for pos, sample_data in data["entries_data"].items():
        pos_data[pos] = {"consensus": defaultdict(list), "mins": defaultdict(list)}

        for sample, (consensus_variant, min_variant, gts, ads) in sample_data.items():
            min_var_freq = 0
            if min_variant and min_variant[0]:
                min_var_mut = f'{pos}_{min_variant[0]}'

                min_var_freq = min_variant[1]
                min_per_sample[sample].append(min_var_mut)
                pos_data[pos]["mins"][min_var_mut].append(min_var_freq)

            pos_data[pos]["consensus"][consensus_variant[0]].append(1 - min_var_freq)
    min_per_sample = dict(min_per_sample)

    df = pd.DataFrame([{"sample": k, "count": len(v)} for k, v in min_per_sample.items()])

    if min_lowfreq:
        cutoff = min_lowfreq
    else:
        median = np.mean(df["count"])
        deviation = np.std(df["count"])
        cutoff = median + deviation_lowfreq * deviation

    candidates = list(df[df["count"] > cutoff]["sample"])
    plt.axvline(cutoff, 0, max(df["count"]), color="red")
    plt.ylabel("Min variant count")
    plt.ylabel("Samples count")

    plt.hist(data=df, x="count")
    plt.savefig(f'{output_dir}/distplot.png')

    dfs = {}
    for c in candidates:
        cdata = []
        for min_var in sorted(min_per_sample[c], key=lambda x: int(x.split("_")[0])):
            pos = min_var.split("_")[0]
            aln_consensus = defaultdict(lambda: 0)
            pos_muts = []
            for sample, (consensus_variant, min_variant, gts, ads) in data["entries_data"][pos].items():

                if sample == c:
                    consensus = consensus_variant[0]
                    min_freq = min_variant[1]
                    min_mut = min_variant[0]
                else:
                    pos_muts.append(consensus_variant[0])
                    if min_variant:
                        pos_muts.append(min_variant[0])
                aln_consensus[consensus_variant[0]] += 1

            sample_exclusive = bool(set([min_var.split("_")[1]]) - set(pos_muts))
            if "n" in aln_consensus:
                del aln_consensus["N"]

            aln_consensus_str = " ".join([f"{k}:{v}" for k, v in aln_consensus.items()])

            if aln_consensus[min_mut] == 1:
                print("NOOO!! : " + str(pos))
                for sample, (consensus_variant, min_variant, gts, ads) in data["entries_data"][pos].items():
                    if consensus_variant == min_mut:
                        print(sample, min_mut, set(pos_muts), min_var)

            r = {"pos": int(pos), "consensus": consensus, "sample_exclusive": sample_exclusive,
                 "dp": sum([int(x) for x in ads.values()]),
                 "min_mut": min_mut, "min_freq": np.round(min_freq, 2), "aln_consensus": aln_consensus_str}
            cdata.append(r)
        dfs[c] = pd.DataFrame(cdata)

    for sample_name, df in dfs.items():
        df.to_csv(f'{output_dir}/{sample_name}.csv', index=False)

    print(f"Report Complete: {len(dfs)} candidate/s were processed")

    return candidates


if __name__ == '__main__':
    import argparse
    import subprocess as sp
    from glob import glob
    import gzip
    from collections import defaultdict

    parser = argparse.ArgumentParser(description='Process minory variants')

    subparsers = parser.add_subparsers(help='commands', description='valid subcommands', dest='command', required=True)

    cmd = subparsers.add_parser('download', help='Downloads reference and sample data')
    cmd.add_argument('-o', '--output_folder', default="./data")
    cmd.add_argument('-v', '--verbose', action='store_true')

    cmd = subparsers.add_parser('bam2vcf', help='calls haplotype caller for each bam sample')
    cmd.add_argument('-bams', '--bams_folder', required=True, help="directory were bam files are located")
    cmd.add_argument('-ref', '--reference', default="data/MN996528.fna",
                     help='fasta file. Can be gziped. Default "data/MN996528.fna"')
    cmd.add_argument('-o', '--output', default="results/", help="output dir. Default resutls/")
    cmd.add_argument('-v', '--verbose', action='store_true')

    cmd = subparsers.add_parser('merge_vcfs', help='joins all haplotype calls in one gvcf')
    cmd.add_argument('-vcfs', '--vcfs_dir', required=True, help="directory were bam files are located")
    cmd.add_argument('-ref', '--reference', default="data/MN996528.fna",
                     help='fasta file. Can be gziped. Default "data/MN996528.fna"')
    cmd.add_argument('-o', '--output',
                     default='results/variants.vcf.gz', help='output file. Default "results/variants.vcf.gz"')
    cmd.add_argument('-v', '--verbose', action='store_true')

    cmd = subparsers.add_parser('minor_freq_vars', help='gets a list of minor freq variants')
    cmd.add_argument('-mad', '--min_allele_depth', default=10, type=int,
                     help='Minimun allele read depth. Default 10')
    cmd.add_argument('-mc', '--min_coverage', default=0.8, type=float,
                     help='max %N to discard a position. Between 0.0-1.0 Default 0.8')
    cmd.add_argument('-mf', '--min_freq', default=0.2, type=float,
                     help='minimun minority variant frequency. Between 0.0-1.0 Default 0.8')
    cmd.add_argument('--vcf', required=True, help="Multi Sample VCF. GT and AD fields are mandatory")
    cmd.add_argument('--out', default="results/data.json", help="Output data")
    cmd.add_argument('-v', '--verbose', action='store_true')

    cmd = subparsers.add_parser('report', help='comparative analysis between samples')
    cmd.add_argument('--data', required=True,
                     help='JSON file created by "minor_freq_vars"')

    cmd.add_argument('--min_lowfreq', default=None,
                     help= 'Instead of using a standard deviation to classify a sample as a coinfection "candidate"'
                     'we use the number of minority variants, as a hard limit. Should be used in a known set of samples '
                           'or if the fact that all samples are candidates is known beforehand. '
                           'If min_lowfreq is active, deviation_lowfreq value is ignored.'
                          )
    cmd.add_argument('--deviation_lowfreq', default=2,
                     help='Coinfection candidates are determined if the number of minority variants are greater than'
                          'N (this parameter) deviations from the mean. Default 2. If min_lowfreq is active, this parameter is ignored ' )

    cmd.add_argument('--out_dir', default="./results")
    cmd.add_argument('-v', '--verbose', action='store_true')

    cmd = subparsers.add_parser('minconsensus', help='creates sequences using minor frequency variants')
    cmd.add_argument('--data', required=True,
                     help='JSON file created by minor_freq_vars')
    cmd.add_argument('--vcf', required=True, help="Multi Sample VCF. GT and AD fields are mandatory")
    cmd.add_argument('--out_dir', default="./results")
    cmd.add_argument('-ref', '--reference', default="data/MN996528.fna",
                     help='fasta file. Can be gziped. Default "data/MN996528.fna"')
    cmd.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    if args.verbose:
        os.environ["verbose"] = "y"

    if args.command == 'download':
        download(args)

    if args.command == 'bam2vcf':

        if not os.path.exists(args.reference):
            sys.stderr.write(f"'{args.reference}' does not exists")
            sys.exit(1)

        outfolder = args.output
        if not os.path.exists(outfolder):
            os.makedirs(outfolder)
        if not os.path.exists(outfolder):
            sys.stderr.write(f"'{outfolder}' could not be created")
            sys.exit(1)

        for bam_file in glob(args.bams_folder + "/*.bam"):
            sample = bam_file.split("/")[-1].split(".bam")[0]
            e(f"samtools index  {bam_file}")
            cmd = f"""/gatk/gatk  HaplotypeCaller -ERC GVCF -R {args.reference} \
                -ploidy 2 -I {bam_file} --output-mode EMIT_ALL_CONFIDENT_SITES -O {args.output}/{sample}.g.vcf.gz"""
            e(cmd)

    if args.command == 'merge_vcfs':
        merge_vcfs(args)

    if args.command == 'minor_freq_vars':
        variant_filter(args)

    if args.command == 'report':
        candidates = comparative_analysis(args.data, args.out_dir, args.deviation_lowfreq, args.min_lowfreq)
        # --sequences_dir ./results/sequences/

    if args.command == 'minconsensus':
        with open("data/combined.vcf") as h, open("./min_seqs.fasta", "w") as output:
            aln(h, output, refseq=str(bpio.read("data/MN996528.fna", "fasta").seq),
                included_samples=candidates)
