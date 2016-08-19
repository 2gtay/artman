# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
import os
import pytest
import execute_pipeline


def get_expected_calls(baseline, binding, stderr=False):
    """Returns the list of expected calls of subprocess.check_output() and
    subprocess.call().

    The expected commandlines are listed in the baseline files located
    under test/testdata, with placeholders of {OUTPUT} for the output dir and
    {CWD} for the current working directory. Those values are supplied from
    binding parameter.
    """
    commands = []
    filename = os.path.join('test', 'testdata', baseline + '.baseline')
    if not os.path.exists(filename):
        return commands
    with open(filename) as f:
        for line in f:
            tokens = line.strip().split()
            if stderr:
                commands.append(mock.call([
                    token.format(**binding) for token in tokens], stderr=-2))
            else:
                commands.append(mock.call([
                    token.format(**binding) for token in tokens]))
    return commands


def format_arg(arg, bindings):
    for (k, v) in bindings.items():
        arg = arg.replace(v, '{' + k + '}')
    return arg


def format_args(args, bindings):
    return ' '.join([format_arg(arg, bindings) for arg in args])


def format_calls(calls, bindings):
    return '\n'.join([format_args(args, bindings)
                      for (name, (args,), kwargs) in calls])


def check_calls_match(expected_calls, actual_calls, bindings):
    mismatch_text = 'Mismatch between expected and actual subprocess calls.\n'

    def format_err(exp, act):
        return mismatch_text + 'Expected:\n' + exp + '\nActual:\n' + act
    exp = format_calls(expected_calls, bindings)
    act = format_calls(actual_calls, bindings)
    assert exp == act, format_err(exp, act)


_DUMMY_FILE_DICT = {
    'java': 'MyApi.java',
    'python': 'my_api.py',
    'go': 'my_api.go',
    'ruby': 'my_api.rb',
    'php': 'MyApi.php',
    'csharp': 'MyApi.cs',
    'nodejs': 'my_api.js'
}


def make_fake_gapic_output(output_dir, language):
    # Create a dummy file in the output_dir. Do not invoke
    # 'touch' command with subprocess.call() because it's mocked.
    dir_head = 'library-v1-gapic-gen-' + language
    final_output_dir = os.path.join(output_dir, dir_head)
    if not os.path.exists(final_output_dir):
        os.makedirs(final_output_dir)
    dummy_file = _DUMMY_FILE_DICT[language]
    with open(os.path.join(final_output_dir, dummy_file), 'w'):
        pass


@mock.patch('pipeline.utils.task_utils.run_gradle_task')
@mock.patch('subprocess.call')
@mock.patch('subprocess.check_call')
@mock.patch('subprocess.check_output')
@mock.patch('os.chdir')
def _test_baseline(pipeline_name, language, config, pipeline_kwargs, baseline,
                   setup_output, mock_chdir, mock_check_output,
                   mock_check_call, mock_call, mock_gradle_task):
    reporoot = os.path.abspath('.')

    # Execute pipeline args
    args = ['--config', config,
            '--pipeline_kwargs', pipeline_kwargs,
            '--reporoot', reporoot,
            pipeline_name]
    if language:
        args += ['--language', language]

    # Mock output value of gradle tasks
    mock_gradle_task.return_value = 'MOCK_GRADLE_TASK_OUTPUT'
    mock_call.return_value = 0
    mock_check_output.return_value = ''

    # Output_dir as defined in artman yaml file
    output_dir = os.path.join(reporoot, 'test/testdata/test_output')

    # Run setup_output function
    if setup_output:
        setup_output(output_dir, language)

    # Run pipeline
    execute_pipeline.main(args)

    bindings = {'CWD': os.getcwd(), 'OUTPUT': output_dir}

    # Compare with the expected subprocess calls.
    expected_checked_calls = get_expected_calls(
        baseline, bindings, True)
    check_calls_match(expected_checked_calls,
                      mock_check_output.mock_calls, bindings)

    # Some tasks can use subprocess.call() instead of check_call(), they are
    # tracked separately.
    expected_subprocess_call = get_expected_calls(
        baseline + '.call', bindings)
    check_calls_match(expected_subprocess_call, mock_call.mock_calls, bindings)


python_pub_kwargs = {
        'repo_url': 'https://example-site.exampledomain.com/',
        'username': 'example-user',
        'password': 'example-pwd',
        'publish_env': 'dev'}


java_pub_kwargs = {
        'repo_url': 'http://maven.example.com/nexus/content/repositories/'
                    'releases',
        'username': 'example-maven-uname',
        'password': 'example-maven-pwd',
        'publish_env': 'prod'}


@pytest.mark.parametrize(
    'pipeline_name, language, extra_kwargs, baseline, setup_output',
    [
        ('GapicConfigPipeline', None, {}, 'config_pipeline', None),
        ('GrpcClientPipeline', 'python', {},
         'python_grpc_client_nopub_pipeline', None),
        ('GrpcClientPipeline', 'python', python_pub_kwargs,
         'python_grpc_client_pub_pipeline', None),
        ('GapicClientPipeline', 'python', {},
         'python_gapic_client_pipeline', make_fake_gapic_output),
        ('CoreProtoPipeline', 'java', {},
         'java_core_proto_nopub_pipeline', None),
        ('CoreProtoPipeline', 'java', java_pub_kwargs,
         'java_core_proto_pub_pipeline', None),
        ('GrpcClientPipeline', 'java', {},
         'java_grpc_client_nopub_pipeline', None),
        ('GrpcClientPipeline', 'java', java_pub_kwargs,
         'java_grpc_client_pub_pipeline', None),
        ('GapicClientPipeline', 'java', {},
         'java_gapic_client_pipeline', make_fake_gapic_output),
        ('GrpcClientPipeline', 'nodejs', {},
         'nodejs_grpc_client_pipeline', None),
        ('GapicClientPipeline', 'nodejs', {},
         'nodejs_gapic_client_pipeline', make_fake_gapic_output),
        ('GrpcClientPipeline', 'ruby', {},
         'ruby_grpc_client_pipeline', None),
        ('GapicClientPipeline', 'ruby', {},
         'ruby_gapic_client_pipeline', make_fake_gapic_output),
        ('GrpcClientPipeline', 'go', {},
         'go_grpc_client_pipeline', None),
        ('GapicClientPipeline', 'go', {},
         'go_gapic_client_pipeline', make_fake_gapic_output),
        ('GrpcClientPipeline', 'php', {},
         'php_grpc_client_pipeline', None),
        ('GapicClientPipeline', 'php', {},
         'php_gapic_client_pipeline', make_fake_gapic_output),
        ('GrpcClientPipeline', 'csharp', {},
         'csharp_grpc_client_pipeline', None),
        ('GapicClientPipeline', 'csharp', {},
         'csharp_gapic_client_pipeline', make_fake_gapic_output),
    ])
def test_generator(pipeline_name, language, extra_kwargs, baseline,
                   setup_output):
    artman_api_yaml = 'test/testdata/googleapis_test/gapic/api/' \
                      'artman_library.yaml'
    artman_language_yaml = 'test/testdata/googleapis_test/gapic/lang/' \
                           'common.yaml'
    config = ','.join([artman_api_yaml, artman_language_yaml])

    pipeline_kwargs = str(extra_kwargs)
    _test_baseline(pipeline_name, language, config, pipeline_kwargs, baseline,
                   setup_output)
