#!/usr/bin/python
"""
  (C) Copyright 2020 Intel Corporation.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  GOVERNMENT LICENSE RIGHTS-OPEN SOURCE SOFTWARE
  The Government's rights to use, modify, reproduce, release, perform, display,
  or disclose this software are subject to the terms of the Apache License as
  provided in Contract No. B609815.
  Any reproduction of computer software, computer software documentation, or
  portions thereof marked with this legend must also reproduce the markings.
"""
from distutils.spawn import find_executable
import os

from command_utils import ExecutableCommand
from command_utils_base import FormattedParameter, EnvironmentVariables
from env_modules import load_mpi
from write_host_file import write_host_file


class JobManager(ExecutableCommand):
    """A class for commands with parameters that manage other commands."""

    def __init__(self, namespace, command, job, path="", subprocess=False):
        """Create a JobManager object.

        Args:
            namespace (str): yaml namespace (path to parameters)
            command (str): string of the command to be executed.
            job (ExecutableCommand): command object to manage.
            path (str, optional): path to location of command binary file.
                Defaults to "".
            subprocess (bool, optional): whether the command is run as a
                subprocess. Defaults to False.
        """
        super(JobManager, self).__init__(namespace, command, path, subprocess)
        self.job = job

    def __str__(self):
        """Return the command with all of its defined parameters as a string.

        Returns:
            str: the command with all the defined parameters

        """
        commands = [super(JobManager, self).__str__(), str(self.job)]
        return " ".join(commands)

    def check_subprocess_status(self, sub_process):
        """Verify command status when called in a subprocess.

        Args:
            sub_process (process.SubProcess): subprocess used to run the command

        Returns:
            bool: whether or not the command progress has been detected

        """
        return self.job.check_subprocess_status(sub_process)

    # deprecated: Use assign_[hosts|processes|environment]() methods instead
    def setup_command(self, env, hostfile, processes):
        """Set up the job manager command with common inputs.

        Args:
            env (EnvironmentVariables): the environment variables to use with
                the launch command
            hostfile (str): file defining host names and slots
            processes (int): number of host processes
        """
        pass

    def assign_hosts(self, hosts, path=None, slots=None):
        """Assign the hosts to use with the command.

        Set the appropriate command line parameter with the specified value.

        Args:
            hosts (list): list of hosts to specify on the command line
            path (str, optional): path to use when specifying the hosts through
                a hostfile. Defaults to None.
            slots (int, optional): number of slots per host to specify in the
                optional hostfile. Defaults to None.
        """
        pass

    def assign_processes(self, processes):
        """Assign the number of processes per node.

        Set the appropriate command line parameter with the specified value.

        Args:
            processes (int): number of processes per node
        """
        pass

    def assign_environment(self, env_vars, append=False):
        """Assign or add environment variables to the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to use
                assign or add to the command
            append (bool): whether to assign (False) or append (True) the
                specified environment variables
        """
        pass

    def assign_environment_default(self, env_vars):
        """Assign the default environment variables for the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to
                assign as the default
        """
        pass


class Orterun(JobManager):
    """A class for the orterun job manager command."""

    def __init__(self, job, subprocess=False):
        """Create a Orterun object.

        Args:
            job (ExecutableCommand): command object to manage.
            subprocess (bool, optional): whether the command is run as a
                subprocess. Defaults to False.
        """
        load_mpi("openmpi")
        path = os.path.dirname(find_executable("orterun"))
        super(Orterun, self).__init__(
            "/run/orterun", "orterun", job, path, subprocess)

        # Default mca values to avoid queue pair errors
        mca_default = {
            "btl_openib_warn_default_gid_prefix": "0",
            "btl": "tcp,self",
            "oob": "tcp",
            "pml": "ob1",
        }

        self.hostfile = FormattedParameter("--hostfile {}", None)
        self.processes = FormattedParameter("--np {}", 1)
        self.display_map = FormattedParameter("--display-map", False)
        self.map_by = FormattedParameter("--map-by {}", "node")
        self.export = FormattedParameter("-x {}", None)
        self.enable_recovery = FormattedParameter("--enable-recovery", True)
        self.report_uri = FormattedParameter("--report-uri {}", None)
        self.allow_run_as_root = FormattedParameter("--allow-run-as-root", None)
        self.mca = FormattedParameter("--mca {}", mca_default)
        self.pprnode = FormattedParameter("--map-by ppr:{}:node", None)
        self.tag_output = FormattedParameter("--tag-output", True)
        self.ompi_server = FormattedParameter("--ompi-server {}", None)

    # deprecated: Use assign_[hosts|processes|environment]() methods instead
    def setup_command(self, env, hostfile, processes):
        """Set up the orterun command with common inputs.

        Args:
            env (EnvironmentVariables): the environment variables to use with
                the launch command
            hostfile (str): file defining host names and slots
            processes (int): number of host processes
        """
        # Setup the env for the job to export with the orterun command
        if self.export.value is None:
            self.export.value = []
        self.export.value.extend(env.get_list())

        # Setup the orterun command
        self.hostfile.value = hostfile
        self.processes.value = processes

    def assign_hosts(self, hosts, path=None, slots=None):
        """Assign the hosts to use with the command (--hostfile).

        Args:
            hosts (list): list of hosts to specify in the hostfile
            path (str, optional): hostfile path. Defaults to None.
            slots (int, optional): number of slots per host to specify in the
                hostfile. Defaults to None.
        """
        kwargs = {"hostlist": hosts, "slots": slots}
        if path is not None:
            kwargs["path"] = path
        self.hostfile.value = write_host_file(**kwargs)

    def assign_processes(self, processes):
        """Assign the number of processes per node (-np).

        Args:
            processes (int): number of processes per node
        """
        self.processes.value = processes

    def assign_environment(self, env_vars, append=False):
        """Assign or add environment variables to the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to use
                assign or add to the command
            append (bool): whether to assign (False) or append (True) the
                specified environment variables
        """
        if append and self.export.value is not None:
            # Convert the current list of environmental variable assignments
            # into an EnvironmentVariables (dict) object.  Then update the
            # dictionary keys with the specified values or add new key value
            # pairs to the dictionary.  Finally convert the updated dictionary
            # back to a list for the parameter assignment.
            original = EnvironmentVariables({
                item.split("=")[0]: item.split("=")[1] if "=" in item else None
                for item in self.export.value})
            original.update(env_vars)
            self.export.value = original.get_list()
        else:
            # Overwrite the environmental variable assignment
            self.export.value = env_vars.get_list()

    def assign_environment_default(self, env_vars):
        """Assign the default environment variables for the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to
                assign as the default
        """
        self.export.update_default(env_vars.get_list())

    def run(self):
        """Run the orterun command.

        Raises:
            CommandFailure: if there is an error running the command

        """
        load_mpi("openmpi")
        return super(Orterun, self).run()


class Mpirun(JobManager):
    """A class for the mpirun job manager command."""

    def __init__(self, job, subprocess=False, mpitype="openmpi"):
        """Create a Mpirun object.

        Args:
            job (ExecutableCommand): command object to manage.
            subprocess (bool, optional): whether the command is run as a
                subprocess. Defaults to False.
        """
        load_mpi(mpitype)
        path = os.path.dirname(find_executable("mpirun"))
        super(Mpirun, self).__init__(
            "/run/mpirun", "mpirun", job, path, subprocess)

        self.hostfile = FormattedParameter("-hostfile {}", None)
        self.processes = FormattedParameter("-np {}", 1)
        self.ppn = FormattedParameter("-ppn {}", None)
        self.envlist = FormattedParameter("-envlist {}", None)
        self.mpitype = mpitype

    # deprecated: Use assign_[hosts|processes|environment]() methods instead
    def setup_command(self, env, hostfile, processes):
        """Set up the mpirun command with common inputs.

        Args:
            env (EnvironmentVariables): the environment variables to use with
                the launch command
            hostfile (str): file defining host names and slots
            processes (int): number of host processes
        """
        # Setup the env for the job to export with the mpirun command
        self._pre_command = env.get_export_str()

        # Setup the orterun command
        self.hostfile.value = hostfile
        self.processes.value = processes

    def assign_hosts(self, hosts, path=None, slots=None):
        """Assign the hosts to use with the command (-f).

        Args:
            hosts (list): list of hosts to specify in the hostfile
            path (str, optional): hostfile path. Defaults to None.
            slots (int, optional): number of slots per host to specify in the
                hostfile. Defaults to None.
        """
        kwargs = {"hostlist": hosts, "slots": slots}
        if path is not None:
            kwargs["path"] = path
        self.hostfile.value = write_host_file(**kwargs)

    def assign_processes(self, processes):
        """Assign the number of processes per node (-np).

        Args:
            processes (int): number of processes per node
        """
        self.processes.value = processes

    def assign_environment(self, env_vars, append=False):
        """Assign or add environment variables to the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to use
                assign or add to the command
            append (bool): whether to assign (False) or append (True) the
                specified environment variables
        """
        if append and self.envlist.value is not None:
            # Convert the current list of environmental variable assignments
            # into an EnvironmentVariables (dict) object.  Then update the
            # dictionary keys with the specified values or add new key value
            # pairs to the dictionary.  Finally convert the updated dictionary
            # back to a string for the parameter assignment.
            original = EnvironmentVariables({
                item.split("=")[0]: item.split("=")[1] if "=" in item else None
                for item in self.envlist.value.split(",")})
            original.update(env_vars)
            self.envlist.value = ",".join(original.get_list())
        else:
            # Overwrite the environmental variable assignment
            self.envlist.value = ",".join(env_vars.get_list())

    def assign_environment_default(self, env_vars):
        """Assign the default environment variables for the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to
                assign as the default
        """
        self.envlist.update_default(env_vars.get_list())

    def run(self):
        """Run the mpirun command.

        Raises:
            CommandFailure: if there is an error running the command

        """
        load_mpi(self.mpitype)
        return super(Mpirun, self).run()


class Srun(JobManager):
    """A class for the srun job manager command."""

    def __init__(self, job, path="", subprocess=False):
        """Create a Srun object.

        Args:
            job (ExecutableCommand): command object to manage.
            path (str, optional): path to location of command binary file.
                Defaults to "".
            subprocess (bool, optional): whether the command is run as a
                subprocess. Defaults to False.
        """
        super(Srun, self).__init__("/run/srun", "srun", job, path, subprocess)

        self.label = FormattedParameter("--label", False)
        self.mpi = FormattedParameter("--mpi={}", None)
        self.export = FormattedParameter("--export={}", None)
        self.ntasks = FormattedParameter("--ntasks={}", None)
        self.distribution = FormattedParameter("--distribution={}", None)
        self.nodefile = FormattedParameter("--nodefile={}", None)
        self.nodelist = FormattedParameter("--nodelist={}", None)
        self.ntasks_per_node = FormattedParameter("--ntasks-per-node={}", None)
        self.reservation = FormattedParameter("--reservation={}", None)
        self.partition = FormattedParameter("--partition={}", None)
        self.output = FormattedParameter("--output={}", None)

    # deprecated: Use assign_[hosts|processes|environment]() methods instead
    def setup_command(self, env, hostfile, processes):
        """Set up the srun command with common inputs.

        Args:
            env (EnvironmentVariables): the environment variables to use with
                the launch command
            hostfile (str): file defining host names and slots
            processes (int): number of host processes
            processpernode (int): number of process per node
        """
        # Setup the env for the job to export with the srun command
        self.export.value = ",".join(["ALL"] + env.get_list())

        # Setup the srun command
        self.label.value = True
        self.mpi.value = "pmi2"
        if processes is not None:
            self.ntasks.value = processes
            self.distribution.value = "cyclic"
        if hostfile is not None:
            self.nodefile.value = hostfile

    def assign_hosts(self, hosts, path=None, slots=None):
        """Assign the hosts to use with the command (-f).

        Args:
            hosts (list): list of hosts to specify in the hostfile
            path (str, optional): hostfile path. Defaults to None.
            slots (int, optional): number of slots per host to specify in the
                hostfile. Defaults to None.
        """
        kwargs = {"hostlist": hosts, "slots": None}
        if path is not None:
            kwargs["path"] = path
        self.nodefile.value = write_host_file(**kwargs)
        self.ntasks_per_node.value = slots

    def assign_processes(self, processes):
        """Assign the number of processes per node (--ntasks).

        Args:
            processes (int): number of processes per node
        """
        self.ntasks.value = processes
        self.distribution.value = "cyclic"

    def assign_environment(self, env_vars, append=False):
        """Assign or add environment variables to the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to use
                assign or add to the command
            append (bool): whether to assign (False) or append (True) the
                specified environment variables
        """
        if append and self.export.value is not None:
            # Convert the current list of environmental variable assignments
            # into an EnvironmentVariables (dict) object.  Then update the
            # dictionary keys with the specified values or add new key value
            # pairs to the dictionary.  Finally convert the updated dictionary
            # back to a string for the parameter assignment.
            original = EnvironmentVariables({
                item.split("=")[0]: item.split("=")[1] if "=" in item else None
                for item in self.export.value.split(",")})
            original.update(env_vars)
            self.export.value = ",".join(original.get_list())
        else:
            # Overwrite the environmental variable assignment
            self.export.value = ",".join(env_vars.get_list())

    def assign_environment_default(self, env_vars):
        """Assign the default environment variables for the command.

        Args:
            env_vars (EnvironmentVariables): the environment variables to
                assign as the default
        """
        self.export.update_default(env_vars.get_list())
