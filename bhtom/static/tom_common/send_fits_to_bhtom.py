#!/usr/bin/env python3 

### BHTOM system script
### Script allows to upload bulk FITS data to BHTOM server.
### Last modified: Feb 22, 2022
### Authors: PM, PT

import os
import subprocess
import requests
import time
import argparse
import sys

bhtom_url = "https://bh-tom.astrolabs.pl/photometry-upload/"

def input_arguments(): 
    global indir, inhash, inobject, infilter, intype, dryrun, inmjd, matching_radius
    des = ">>> " + os.path.basename(sys.argv[0]) + " <<<\n" + \
          "Sends image data to BHTOM system\n" + \
          "Requires: Python3 with os,subprocess,requests,time,\n" + \
          "          argparse,sys packages\n" + \
          "Example: send_to_bhtom.py -d ./files_to_be_sent -o Gaia18dif -ht bhtom_LCOGT-SS-1m_4K_peteruk2_88d7c27083cfb51af71\n" + \
          "[-f filter] [-r matching_radius] --dryrun"
    parser = argparse.ArgumentParser(description = des, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-d", "--dir", type=str, help="directory containing FITS images or a PHOT filepath", required=True)
    parser.add_argument("-ht", "--hashtag", type=str, help="your dedicated hashtag", required=True)
    parser.add_argument("-o", "--object", type=str, help="object name", required=True)
    parser.add_argument("-f", "--filter", type=str, help="matching catalogue filter name", default=False)
    parser.add_argument("-r", "--radius", type=float, help="matching radius size", default=2.0)
    parser.add_argument("--dryrun", help="sends data, but does not store datapoints in BHTOM database", action="store_true") 
    args = parser.parse_args()
    indir       = str(args.dir)
    inhash      = str(args.hashtag)
    inobject    = str(args.object) 
    infilter    = str(args.filter)
    dryrun      = True if args.dryrun else False
    matching_radius = float(args.radius)

def show_arguments():
    print("$ Directory              :", indir)
    print("$ Hashtag                :", inhash)
    print("$ Object name            :", inobject)
    print("$ Matching filter        :", infilter)
    print("$ Dry run                :", dryrun)

def send_fits_file(filename,hashtag,target,flter,m_radius,dry_run):
    with open(os.path.join(indir, filename), 'rb') as f:
        if flter == False:
            response = requests.post(
            url = bhtom_url,
                headers={
                'hashtag': hashtag
                },
                data={
                'target': target,
                'data_product_type':  'fits_file',
                'matching_radius': str(m_radius),
                'dry_run': dry_run
                 },
                 files={'files': f}
              )
        else:
            response = requests.post(
            url = bhtom_url,
                headers={
                'hashtag': hashtag
                },
                data={
                'target': target,
                'filter': flter,
                'data_product_type':  'fits_file',
                'matching_radius': str(m_radius),
                'dry_run': dry_run
                 },
                 files={'files': f}
              )
        server_response = response.status_code
        ## print(response, server_response)
        return response, server_response

if __name__ == '__main__':
    print("")
    input_arguments()
    show_arguments()   

    number_of_files = len(os.listdir(indir))
    if number_of_files > 0:
        print("\n$$$ NOW SENDING DATA TO BHTOM (https://bh-tom.astrolabs.pl) $$$\n")
    else:
        print("\n# No files present inside '" + str(indir) + "'")
        print("  Program is terminating.\n")
        sys.exit(1)
        
    i       = 0
    success = 0
    error   = 0
    total   = number_of_files
    for filename in os.listdir(indir):
        i += 1
        total -= 1
        prompt = "$ LEFT: " + str(total + 1) + " | SUCCESS: " + str(success) + " | ERROR: " + str(error) + " | " + \
                 "> Now uploading '" + str(filename) + "' (" + str(i) + "/" + str(number_of_files) + ")               "
        print(prompt, end="\r")
        msg, code = send_fits_file(filename, inhash, inobject, infilter, matching_radius, dryrun)
        if code == 200:
            success += 1
            subprocess.call('mkdir success 2>/dev/null', shell=True)
            subprocess.call("mv %s/%s %s " % (indir, filename, "./success/"), shell=True)
        else:
            error += 1
            subprocess.call('mkdir error 2>/dev/null', shell=True)
            subprocess.call("cp %s/%s %s " % (indir, filename, "./error/"), shell=True)
        time.sleep(0.01)
    print("$ LEFT: " + str(total) + " | SUCCESS: " + str(success) + " | ERROR: " + str(error) + \
          "                                                              ")
    print("$ All files have been processed.")
    if success > 0:
        print("  Files processed successfully have been moved to 'success' directory.")
    if error > 0:
        print("  Files with errors have been copied to 'error' directory.")
    print("$ Thank you for using BHTOM!")
    print("  Program is terminating.\n")
    sys.exit(0)