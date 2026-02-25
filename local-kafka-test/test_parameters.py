# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Modified for local Kafka testing
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import re
import os
import math
import random
import json
from typing import Dict, List, Any, Optional, Tuple

random.seed()


def increment_index_and_update_parameters(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Increment the test index and update parameters for the next test.

    Args:
        event: Current test event containing test_specification and optionally current_test

    Returns:
        Updated event with new parameters
    """
    test_specification = event["test_specification"]

    if "current_test" in event:
        previous_test_index = event["current_test"]["index"]
        skip_condition = test_specification.get("skip_remaining_throughput")

        try:
            # Only evaluate skip condition if we have a producer_result from the previous test
            if skip_condition and "producer_result" in event and event["producer_result"]:
                if evaluate_skip_condition(skip_condition, event):
                    # Skip remaining throughput values
                    (updated_test_index, throughput_series_id) = skip_remaining_throughput(previous_test_index, event)
                else:
                    # Increment to next test configuration
                    (updated_test_index, throughput_series_id) = increment_test_index(previous_test_index, event, 0)
            else:
                # No skip condition or no producer_result, just increment
                (updated_test_index, throughput_series_id) = increment_test_index(previous_test_index, event, 0)
        except OverflowError:
            # All tests have been executed
            updated_test_index = None
            throughput_series_id = random.randint(0, 100000)
    else:
        # First test - start with the first index
        updated_test_index = {key: 0 for key in test_specification["parameters"].keys()}
        throughput_series_id = random.randint(0, 100000)

    return update_parameters(test_specification, updated_test_index, random.randint(0, 100000), throughput_series_id)


def evaluate_skip_condition(condition: Any, event: Dict[str, Any]) -> float:
    """
    Evaluate the skip condition for test parameters.
    
    Args:
        condition: Skip condition (dict with greater-than/less-than, string metric name, or numeric value)
        event: Current test event
        
    Returns:
        Evaluated condition value
    """
    if isinstance(condition, dict):
        if "greater-than" in condition:
            args = condition["greater-than"]
            return evaluate_skip_condition(args[0], event) > evaluate_skip_condition(args[1], event)
        elif "less-than" in condition:
            args = condition["less-than"]
            return evaluate_skip_condition(args[0], event) < evaluate_skip_condition(args[1], event)
        else:
            raise Exception("Unable to parse condition: " + str(condition))
    elif isinstance(condition, str):
        if condition == "sent_div_requested_mb_per_sec":
            producer_result = event.get("producer_result", {})
            mb_per_sec_sum = producer_result.get("mbPerSecSum", 0)
            requested_throughput = event["current_test"]["parameters"]["cluster_throughput_mb_per_sec"]
            if requested_throughput <= 0:
                return 1.0
            return mb_per_sec_sum / requested_throughput
        else:
            raise Exception("Unable to parse condition: " + condition)
    elif isinstance(condition, (int, float)):
        return float(condition)
    else:
        raise Exception("Unable to parse condition: " + str(condition))


def increment_test_index(index: Dict[str, int], event: Dict[str, Any], pos: int) -> Tuple[Dict[str, int], int]:
    """
    Increment the test index to the next configuration.
    
    Args:
        index: Current test index
        event: Current test event
        pos: Position in parameter list
        
    Returns:
        Tuple of (updated index, throughput series ID)
    """
    parameters = list(event["test_specification"]["parameters"].keys())

    if not (0 <= pos < len(parameters)):
        raise OverflowError("All test configurations exhausted")

    paramater_name = parameters[pos]
    parameter_value = index.get(paramater_name, 0)

    if parameter_value + 1 < len(event["test_specification"]["parameters"][paramater_name]):
        # Increment this parameter
        return ({**index, paramater_name: parameter_value + 1}, 
                event["current_test"]["parameters"]["throughput_series_id"])
    else:
        # Reset this parameter and increment the next one
        if paramater_name == "cluster_throughput_mb_per_sec":
            # Reset throughput and update series ID
            (updated_index, _) = increment_test_index({**index, paramater_name: 0}, event, pos + 1)
            updated_throughput_series_id = random.randint(0, 100000)
            return (updated_index, updated_throughput_series_id)
        else:
            return increment_test_index({**index, paramater_name: 0}, event, pos + 1)


def update_parameters(test_specification: Dict[str, Any], 
                     updated_test_index: Optional[Dict[str, int]], 
                     test_id: int, 
                     throughput_series_id: int) -> Dict[str, Any]:
    """
    Update test parameters based on the current index.
    
    Args:
        test_specification: Test specification
        updated_test_index: Current test index (None if all tests completed)
        test_id: Test ID
        throughput_series_id: Throughput series ID
        
    Returns:
        Updated event with parameters
    """
    if updated_test_index is None:
        # All tests completed
        return {
            "test_specification": test_specification,
            "all_tests_completed": True
        }
    else:
        # Get the new parameters for the updated index
        updated_parameters = {
            index_name: test_specification["parameters"][index_name][index_value] 
            for (index_name, index_value) in updated_test_index.items()
        }

        # Encode the current index into the topic name
        max_topic_property_length = 15
        remove_invalid_chars = lambda x: re.sub(r'[^a-zA-Z0-9-]', '-', x.replace(' ', '-'))

        topic_name = (f'test-id-{test_id}--throughput-series-id-{throughput_series_id}--' + 
                     '--'.join([f"{remove_invalid_chars(k)[:max_topic_property_length]}-{v}" 
                               for k, v in updated_test_index.items()]))
        depletion_topic_name = f'test-id-{test_id}--throughput-series-id-{throughput_series_id}--depletion'

        record_size_byte = updated_parameters["record_size_byte"]

        if updated_parameters["cluster_throughput_mb_per_sec"] > 0:
            producer_throughput_byte = (updated_parameters["cluster_throughput_mb_per_sec"] * 1024**2 // 
                                       updated_parameters["num_producers"])
            consumer_throughput_byte = (updated_parameters["cluster_throughput_mb_per_sec"] * 1024**2 // 
                                       updated_parameters["consumer_groups"]["size"] 
                                       if updated_parameters["consumer_groups"]["size"] > 0 else 0)

            num_records_producer = producer_throughput_byte * updated_parameters["duration_sec"] // record_size_byte
            num_records_consumer = consumer_throughput_byte * updated_parameters["duration_sec"] // record_size_byte
        else:
            # For depletion, publish messages as fast as possible
            producer_throughput_byte = -1
            consumer_throughput_byte = -1
            num_records_producer = 2147483647
            num_records_consumer = 2147483647

        # Derive additional parameters
        updated_parameters = {
            **updated_parameters,
            "num_jobs": (updated_parameters["num_producers"] + 
                        updated_parameters["consumer_groups"]["num_groups"] * updated_parameters["consumer_groups"]["size"]),
            "producer_throughput": producer_throughput_byte,
            "records_per_sec": max(1, producer_throughput_byte // record_size_byte) if producer_throughput_byte > 0 else -1,
            "num_records_producer": num_records_producer,
            "num_records_consumer": num_records_consumer,
            "test_id": test_id,
            "throughput_series_id": throughput_series_id,
            "topic_name": topic_name,
            "depletion_topic_name": depletion_topic_name
        }

        updated_event = {
            "test_specification": test_specification,
            "current_test": {
                "index": updated_test_index,
                "parameters": updated_parameters
            }
        }

        return updated_event


def skip_remaining_throughput(index: Dict[str, int], event: Dict[str, Any]) -> Tuple[Dict[str, int], int]:
    """
    Skip remaining throughput values and move to next configuration.
    
    Args:
        index: Current test index
        event: Current test event
        
    Returns:
        Tuple of (updated index, new throughput series ID)
    """
    parameters = list(event["test_specification"]["parameters"].keys())
    throughput_index = parameters.index("cluster_throughput_mb_per_sec")

    # Reset all parameters up to cluster_throughput_mb_per_sec to 0
    reset_index = {
        index_name: 0 for i, index_name in enumerate(index) if i <= throughput_index
    }

    # Keep values of other parameters and increase next parameter
    (updated_index, _) = increment_test_index({**index, **reset_index}, event, pos=throughput_index + 1)

    # Choose new series ID
    throughput_series_id = random.randint(0, 100000)

    return (updated_index, throughput_series_id)


def update_parameters_for_depletion(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update parameters for credit depletion phase.
    
    Args:
        event: Current test event
        
    Returns:
        Updated event with depletion parameters
    """
    test_specification = event["test_specification"]
    test_parameters = test_specification["parameters"]
    test_index = event["current_test"]["index"]
    test_id = event["current_test"]["parameters"]["test_id"]
    throughput_series_id = event["current_test"]["parameters"]["throughput_series_id"]
    depletion_duration_sec = test_specification["depletion_configuration"]["approximate_timeout_hours"] * 60 * 60

    # Overwrite throughput with -1 for credit depletion
    depletion_parameters = {
        **test_parameters,
        "duration_sec": [depletion_duration_sec] * len(test_parameters["duration_sec"]),
        "cluster_throughput_mb_per_sec": [-1] * len(test_parameters["cluster_throughput_mb_per_sec"]),
    }

    return update_parameters({**test_specification, "parameters": depletion_parameters}, 
                            test_index, test_id, throughput_series_id)


def load_test_specification(spec_path: str) -> Dict[str, Any]:
    """
    Load test specification from JSON file.
    
    Args:
        spec_path: Path to test specification JSON file
        
    Returns:
        Test specification dictionary
    """
    with open(spec_path, 'r') as f:
        return json.load(f)


def save_test_specification(spec: Dict[str, Any], spec_path: str) -> None:
    """
    Save test specification to JSON file.
    
    Args:
        spec: Test specification dictionary
        spec_path: Path to save specification
    """
    with open(spec_path, 'w') as f:
        json.dump(spec, f, indent=2)


def get_all_test_configurations(spec_path: str) -> List[Dict[str, Any]]:
    """
    Generate all test configurations from a test specification.
    
    Args:
        spec_path: Path to test specification JSON file
        
    Returns:
        List of all test configurations
    """
    event = load_test_specification(spec_path)
    configurations = []
    
    while True:
        event = increment_index_and_update_parameters(event)
        
        if event.get("all_tests_completed", False):
            break
            
        configurations.append(event["current_test"]["parameters"])
    
    return configurations
