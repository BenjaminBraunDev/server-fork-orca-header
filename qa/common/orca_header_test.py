#!/usr/bin/python3
# Copyright 2023-2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys

sys.path.append("../common")

import argparse
import json
import os
import requests

# To run the test, have tritonserver running and run this script with the endpoint as a flag.
#
# Example:
# ```
# python3 orca_header_test.py http://localhost:8000/v2/models/ensemble/generate
# ```
def get_endpoint_header(url, data):
    """
    Sends a POST request to the given URL with the provided data and returns the value of the "endpoint-load-metrics" header,
    or None if the request fails.
    """
    HEADER_KEY = "endpoint-load-metrics"
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.headers.get(HEADER_KEY, "")
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None

def parse_header_data(header, orca_format):
    """
    Parses the header data into a dictionary based on the given format.
    """
    METRIC_KEY = "named_metrics"
    try:
        if orca_format == "json":
            # Parse the header in JSON format
            data = json.loads(header.replace("JSON ", ""))
            if METRIC_KEY in data:
                return data[METRIC_KEY]
            else:
                print(f"No key '{METRIC_KEY}' in header data: {data}")
                return None
            return data
        elif orca_format == "http":
            # Parse the header in TEXT format
            data = {}
            for key_value_pair in header.replace("TEXT ", "").split(", "):
                key, value = key_value_pair.split("=")
                if "." in key:
                    prefix, nested_key = key.split(".", 1)
                    if prefix == METRIC_KEY:
                        data[nested_key] = float(value)
            if not data:
                print(f"Could not parse any keys from header: {header}")
                return None
            return data
        else:
            print(f"Invalid ORCA format: {orca_format}")
            return None
    except (json.JSONDecodeError, ValueError, KeyError):
        print("Error: Invalid data in the header.")
        return None

def check_for_keys(data, desired_keys, orca_format):
    """
    Checks if all desired keys are present in the given data dictionary.
    """
    if all(key in data for key in desired_keys):
        print(f"ORCA header present in {orca_format} format with kv_cache_utilization: {[k + ": " + str(data[k]) for k in desired_keys]}")
        return True
    else:
        print(f"Missing keys in header: {', '.join(set(desired_keys) - set(data))}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make a POST request to generate endpoint to test the ORCA metrics header.")
    parser.add_argument("url", help="The model URL to send the request to.")
    args = parser.parse_args()

    TEST_DATA = json.loads('{"text_input": "hello world", "max_tokens": 20, "bad_words": "", "stop_words": ""}')
    ORCA_ENVVAR = "TRITON_ORCA_METRIC_FORMAT"
    orca_format = os.environ.get(ORCA_ENVVAR, "")

    header = get_endpoint_header(args.url, TEST_DATA)
    desired_keys = {"kv_cache_utilization", "max_token_capacity"}  # Just the keys, no need to initialize with None
    passed = None

    if header is None:
        print(f"Request to endpoint: '{args.url}' failed.")
        passed = False
    elif orca_format in ["json", "http"]:
        data = parse_header_data(header, orca_format)
        if data:
            passed = check_for_keys(data, desired_keys, orca_format)
    elif header == "":
        if orca_format:
            print(f"header empty, {ORCA_ENVVAR}={orca_format} is not a valid ORCA metric format")
        else:
            print(f"header empty, {ORCA_ENVVAR} is not set")
        passed = True
    else:
        print(f"Unexpected header value: {header}")
        passed = False
    
    sys.exit(0 if passed else 1)