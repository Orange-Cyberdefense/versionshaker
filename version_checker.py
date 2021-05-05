#!/bin/env python3
# coding: utf-8

import argparse
import requests
import os
import sys
from rich import print
from rich.progress import Progress
from rich.table import Table
from rich.console import Console
from os.path import isfile
from git import Repo
from difflib import SequenceMatcher
from urllib3.exceptions import InsecureRequestWarning

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


def parser():
    parser = argparse.ArgumentParser(
        description='Version checker 0.1',
        epilog='Example : python3 version_checker.py -c https://github.com/repo -u http://url/ -f js/admin.js,js/tools.js')
    parser.add_argument('-u', '--url', help="target url ended with a /", required=True)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', '--clone', help="git url to clone locally")
    group.add_argument('-l', '--local', help="local git repository to compare")

    group2 = parser.add_mutually_exclusive_group(required=True)
    # group2.add_argument('-x', '--extensions', help="Extensions to check (default : js,css)", required=False)
    group2.add_argument('-f', '--files',
                        help="files relative path separated by ,",
                        required=False)

    parser.add_argument('-t', '--tags', help="force tags to use coma separated", required=False)
    parser.add_argument('-p', '--path', help="git repository web folder location (useful in case of public folder)",
                        required=False)
    parser.add_argument('-v', '--verbose', help="Give more verbosity", action="store_true")
    parser.add_argument('-P', '--proxy', help="use proxy to launch request to url", required=False)
    return parser.parse_args()


def color_ratio(ratio):
    """
    define the color for ratio
    :param ratio:
    :return: string (color)
    """
    if ratio == 100:
        color = 'green'
    elif ratio >= 95:
        color = 'blue'
    elif ratio >= 90:
        color = 'yellow'
    else:
        color = 'red'
    return color


class VersionChecker:

    def __init__(self, url, git=None, local=None, verbose=False, files=None, extensions=None, proxy=None, tags=None,
                 web_folder=None):
        """
        Init the class
        :param url:  the remote url to check
        :param git: the git repository url to clone
        :param local: the local git repository (precedence on git)
        :param verbose: more output
        :param files: file list to check
        :param extensions: extension list to automatic get files (not implemented yet)
        :param proxy: proxy parameter value
        :param tags: list of tags to check (by default all tags are verified)
        """
        self.url = url
        if self.url[-1:] != '/':
            self.url += '/'
        self.git = git
        self.local = local
        self.verbose = verbose
        self.repo_local_path = '.tmp/'
        if web_folder is None:
            self.web_folder = ''
        if self.web_folder != '':
            if self.web_folder[-1:] != '/':
                self.web_folder += '/'
        if tags is not None:
            self.tags = [x.strip() for x in tags.split(',')]
        else:
            self.tags = None
        self.repo = None
        self.files_to_check = None
        if files is not None:
            self.files = [x.strip() for x in files.split(',')]
            self.extensions = None
        else:
            self.files = None
            if extensions is None:
                self.extensions = ['js', 'css']
            else:
                self.extensions = [x.strip() for x in extensions.split(',')]
        if proxy is not None:
            self.proxy = {
                'http': proxy,
                'https': proxy
            }
        else:
            self.proxy = None

    def clone(self):
        """
        Clone git repository locally inside the .tmp folder
        :return:
        """
        tmp_folder = self.repo_local_path
        print("[blue] Clone the git %s repository [/blue]" % self.git)
        try:
            os.makedirs(tmp_folder)
        except:
            print(
                "[yellow] [-] We use %s to clone repository, this directory already exist[/yellow] " % tmp_folder)
            inp = input("  Delete ? [Y/n] ")
            if inp.lower() == "" or inp.lower() == "y":
                os.system('rm -rf ' + tmp_folder)
                os.makedirs(tmp_folder)
            else:
                self.repo = Repo(tmp_folder)
                return
        print("[blue] [+] Cloning repo please wait... [/blue] ")
        Repo.clone_from(self.git, tmp_folder)
        if self.verbose:
            print("[blue] [+] Cloned ! [/blue]")
        self.repo = Repo(tmp_folder)

    def check_url(self):
        """
        Check the remote URL
        exit if the response code is not 200
        :return: response text
        """
        r = requests.get(self.url, proxies=self.proxy)
        if r.status_code != 200:
            print('[red] url status code %i is not 200 exit [/red]' % r.status_code)
            sys.exit(1)
        return r.text

    def auto_discover_files(self, url_text_content):
        """
        TODO : Automatic static files discovery based on the url and the extensions
        :return: list of valid files
        """
        print('[red] recon not implemented yet [/red]')
        return []

    def check_files_exists(self):
        """
        Check if the files are available on the remote target
        :return: list of files with response code 200
        """
        file_list = []
        for file in self.files:
            r = requests.get(self.url + file, proxies=self.proxy)
            if r.status_code == 200:
                print('[green] [+] file %s found on server [/green]' % file)
                file_list.append((file, r.text))
            else:
                print('[yellow] [-] file %s not found on server skip [/yellow]' % file)
        return file_list

    def process_tag(self, tag_name, files):
        results = {}
        self.repo.git.checkout(tag_name, force=True)
        for (file, text) in files:
            if isfile(self.repo_local_path + self.web_folder + file):
                try:
                    with open(self.repo_local_path + self.web_folder + file, 'r') as f:
                        git_file = f.read().encode('utf-8')
                    web_file = text.encode('utf-8')
                    ratio = SequenceMatcher(None, git_file, web_file).quick_ratio()
                    ratio *= 100.00
                    color = color_ratio(ratio)
                    results[file] = ratio
                    ratio = '[' + color + '] ' + str(ratio) + '[/' + color + ']'
                    if self.verbose:
                        print('[green] %s ratio for file %s is %s[/green]' % (tag_name, file, ratio))
                except UnicodeDecodeError:
                    results[file] = -1
            else:
                if self.verbose:
                    print('[red] file %s not found [/red]' % file)
                results[file] = -1
        return results

    def check_diff(self, tags, files):
        """
        Check the difference between the file on remote and on git tag
        :param tags: list of tags to verify
        :param files: list of files to check
        :return: result dict format : result[tag][file]=ratio
        """
        results = {}
        if not self.verbose:
            with Progress() as progress:
                task1 = progress.add_task("[cyan]checking tags...", total=len(tags))
                for tag_name in tags:
                    results[tag_name] = self.process_tag(tag_name, files)
                    progress.update(task1, advance=1, description='[cyan]Checking tags :[/cyan] %15s' % tag_name)
        else:
            for tag_name in tags:
                if self.verbose:
                    print('[blue] --- tag : %s  --- [/blue]' % tag_name)
                    results[tag_name] = self.process_tag(tag_name, files)
        return results

    def compile_tags_ratio(self, results):
        """
        Compile the results {tag => {file => ratio} } to get the bests match
        :param results:
        :return: dict { tag => ratio checked files}
        """
        bests = {}
        for tag, result in results.items():
            tag_ratio = 0
            nb_files = 0
            for file, ratio in result.items():
                tag_ratio += ratio
                nb_files += 1
            bests[tag] = tag_ratio / nb_files
        return bests

    def compile_tags_ratio_total(self, results, total_files):
        """
        Compile the results {tag => {file => ratio} } to get the bests match
        :param total_files: total number of file to check
        :param results:
        :return: dict { tag => (ratio checked files, ratio total files)}
        """
        bests = {}
        for tag, result in results.items():
            tag_ratio = 0
            nb_files = 0
            for file, ratio in result.items():
                tag_ratio += ratio
                nb_files += 1
            bests[tag] = tag_ratio / total_files
        return bests

    def compile_files_best_tags(self, results):
        """
        Compile the results {tag => {file => ratio} } to get the bests match
        :param results:
        :return: dict { file => ratio, tags}
        """
        bests = {}
        for tag, result in results.items():
            for file, ratio in result.items():
                if file in bests:
                    (best_ratio, best_tag) = bests[file]
                    if ratio > best_ratio:
                        bests[file] = (ratio, tag)
                    elif ratio == best_ratio:
                        bests[file] = (ratio, tag + ', ' + best_tag)
                else:
                    bests[file] = (ratio, tag)
        return bests

    def compile_tag_nb_best_matching_files(self, bests_files):
        """
        Return a tag dict with the number of best match in files checked
        :param bests_files:
        :return: dict : {tag => nb_files_best_match}
        """
        # print tags results
        tag_nb_best_match = {}
        best = 0
        for file, values in bests_files.items():
            (ratio, tags) = values
            for tag in [x.strip() for x in tags.split(',')]:
                if tag not in tag_nb_best_match:
                    tag_nb_best_match[tag] = 1
                else:
                    tag_nb_best_match[tag] += 1
        return tag_nb_best_match

    def compile_find_best_tag(self, tags_ratio_checked, tags_ratio_total, tags_nb_best_match):
        """
        Return a list of best tags based on ratio total, ratio on file checked and nb best file match
        :param tags_ratio_checked:
        :param tags_ratio_total:
        :param tags_nb_best_match:
        :return: list of best tags
        """
        best_tags = []
        best = 0
        max_ratio_checked_tag = max(tags_ratio_checked, key=tags_ratio_checked.get)
        max_ratio_total_tag = max(tags_ratio_total, key=tags_ratio_total.get)

        max_files_match = max(tags_nb_best_match.values())

        for tag, nb in tags_nb_best_match.items():
            if nb == max_files_match:
                best_tags.append(tag)

        best_tags.append(max_ratio_checked_tag)
        best_tags.append(max_ratio_total_tag)
        return best_tags

    def print_results(self, results, nb_files):
        """
        print the check results
        :param nb_files: total files number to check
        :param results: {tag => {file => ratio} }
        """
        bests_files = self.compile_files_best_tags(results)
        tags_ratio_checked = self.compile_tags_ratio(results)
        tags_ratio_total = self.compile_tags_ratio_total(results, nb_files)
        tags_nb_best_match = self.compile_tag_nb_best_matching_files(bests_files)
        best_tags = self.compile_find_best_tag(tags_ratio_checked, tags_ratio_total, tags_nb_best_match)

        print('\n[blue] --- RESULTS by files --- [/blue]')
        for file, value in bests_files.items():
            (ratio, tag) = value
            color = color_ratio(ratio)
            r = '[' + color + '] ' + str(ratio) + '[/' + color + ']'
            print('file %s : %s (%s)' % (file, tag, r))

        console = Console()
        print('\n[blue] --- RESULTS by tags --- [/blue]')
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Tag")
        table.add_column("Ratio on checked files")
        table.add_column("Ratio on all files")
        table.add_column("Number of best choice on %i files" % nb_files)
        for tag, nb_file_best in sorted(tags_nb_best_match.items()):
            tag_ratio_checked = tags_ratio_checked[tag]
            tag_ratio_total = tags_ratio_total[tag]
            ratio_checked = '[' + color_ratio(tag_ratio_checked) + '] ' + str(tag_ratio_checked) + '[/' + color_ratio(
                tag_ratio_checked) + ']'
            ratio_total = '[' + color_ratio(tag_ratio_total) + '] ' + str(tag_ratio_total) + '[/' + color_ratio(
                tag_ratio_total) + ']'
            if tag in best_tags:
                table.add_row('[green]' + tag + '[/green]', ratio_checked, ratio_total,
                              '[green]' + str(nb_file_best) + '[/green]')
            else:
                table.add_row(tag, ratio_checked, ratio_total, str(nb_file_best))
        console.print(table)

    def init_git_repository(self):
        """
        Init the git repository with local folder or clone remote repository
        :return: repository
        """
        if self.local is None:
            self.clone()
        else:
            try:
                self.repo = Repo(self.local)
                if self.local[-1:] != '/':
                    self.repo_local_path = self.local + '/'
                else:
                    self.repo_local_path = self.local
            except:
                print('[red]Local git repository (%s) not found[/red]' % self.local)
                sys.exit(1)
        return self.repo

    def init_files_to_check(self, response):
        """
        Init the file list to check
        :param response:
        :return: list of files path
        """
        if self.files is None:
            self.files_to_check = self.auto_discover_files(response)
        else:
            self.files_to_check = self.check_files_exists()
        return self.files_to_check

    def init_tag_list(self):
        """
        Init the list of tags to check
        :return: list of tags
        """
        if self.tags is not None:
            tags = self.tags
        else:
            tags = [tag.name for tag in self.repo.tags]

        if self.verbose:
            print('[blue] --- tag list --- [/blue]')
            print("[green]" + ", ".join(tags) + "[/green]")
        return tags

    def execute(self):
        """
        run function
        """
        response = self.check_url()
        files = self.init_files_to_check(response)
        self.init_git_repository()
        tags = self.init_tag_list()
        results = self.check_diff(tags, files)
        self.print_results(results, len(files))


if __name__ == "__main__":
    arg = parser()
    checker = VersionChecker(arg.url, arg.clone, arg.local, verbose=arg.verbose, files=arg.files, proxy=arg.proxy,
                             tags=arg.tags, web_folder=arg.path)
    checker.execute()
