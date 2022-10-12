"""Zaza fun tests."""
import asyncio
import base64
import concurrent.futures
import unittest

from tests import utils
from tests.configure import ubuntu_backup_directory_source, ubuntu_user_pass

import zaza.model


def _run(coro):
    """Return result of an async function."""
    return asyncio.get_event_loop().run_until_complete(coro)


class BaseDuplicityTest(unittest.TestCase):
    """Base class for Duplicity charm tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Duplicity tests."""
        cls.model_name = zaza.model.get_juju_model()
        cls.application_name = "duplicity"


class DuplicityBackupCronTest(BaseDuplicityTest):
    """Base class for Duplicity Backup cron job charm tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for Duplicity Backup cron job charm tests."""
        super().setUpClass()

    @utils.config_restore("duplicity")
    def test_cron_creation(self):
        """Verify cron job creation."""
        options = ["daily", "weekly", "monthly"]
        for option in options:
            new_config = dict(backup_frequency=option)
            zaza.model.set_application_config(self.application_name, new_config)
            try:
                zaza.model.block_until_file_has_contents(
                    application_name=self.application_name,
                    remote_file="/etc/cron.d/periodic_backup",
                    expected_contents=option,
                    timeout=60,
                )
            except concurrent.futures._base.TimeoutError:
                self.fail(
                    "Cron file /etc/cron.d/period_backup never populated with "
                    "option <{}>".format(option)
                )

    @utils.config_restore("duplicity")
    def test_cron_creation_cron_string(self):
        """Verify cron job creation."""
        cron_string = "* * * * *"
        new_config = dict(backup_frequency=cron_string)
        zaza.model.set_application_config(self.application_name, new_config)
        try:
            zaza.model.block_until_file_has_contents(
                application_name=self.application_name,
                remote_file="/etc/cron.d/periodic_backup",
                expected_contents=cron_string,
                timeout=60,
            )
        except concurrent.futures._base.TimeoutError:
            self.fail(
                "Cron file /etc/cron.d/period_backup never populated with "
                "option <{}>".format(cron_string)
            )

    @utils.config_restore("duplicity")
    def test_cron_invalid_cron_string(self):
        """Verify cron job creation with invalid frequency."""
        cron_string = "* * * *"
        new_config = dict(backup_frequency=cron_string)
        zaza.model.set_application_config(self.application_name, new_config)
        try:
            duplicity_workload_checker = utils.get_workload_application_status_checker(
                self.application_name, "blocked"
            )
            _run(zaza.model.async_block_until(duplicity_workload_checker, timeout=15))
            a_unit = zaza.model.get_units(self.application_name)[0]
            self.assertEquals(
                a_unit.workload_status_message,
                'Invalid value "{}" for "backup_frequency"'.format(cron_string),
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Failed to enter blocked state with invalid backup_frequency.")

    @utils.config_restore("duplicity")
    def test_no_cron(self):
        """Verify manual or invalid cron job frequency."""
        options = ["manual"]
        for option in options:
            new_config = dict(backup_frequency=option)
            zaza.model.set_application_config(self.application_name, new_config)
            try:
                zaza.model.block_until_file_missing(
                    model_name=self.model_name,
                    app=self.application_name,
                    path="/etc/cron.d/periodic_backup",
                    timeout=60,
                )
            except concurrent.futures._base.TimeoutError:
                self.fail(
                    "Cron file /etc/cron.d/period_backup exists with "
                    "option <{}>".format(option)
                )


class DuplicityEncryptionValidationTest(BaseDuplicityTest):
    """Verify encryption validation."""

    @classmethod
    def setUpClass(cls):
        """Set up encryption validation tests."""
        super().setUpClass()

    @utils.config_restore("duplicity")
    def test_encryption_true_no_key_no_passphrase_blocks(self):
        """Verify unit is blocked with no passphrase or key."""
        new_config = dict(
            encryption_passphrase="", gpg_public_key="", disable_encryption="False"
        )
        zaza.model.set_application_config(
            self.application_name, new_config, self.model_name
        )
        try:
            duplicity_workload_checker = utils.get_workload_application_status_checker(
                self.application_name, "blocked"
            )
            _run(zaza.model.async_block_until(duplicity_workload_checker, timeout=15))
            a_unit = zaza.model.get_units(self.application_name)[0]
            self.assertEquals(
                a_unit.workload_status_message,
                "Must set either an encryption passphrase, GPG public key, "
                "or disable encryption",
            )
        except concurrent.futures._base.TimeoutError:
            self.fail(
                "Failed to enter blocked state with encryption enables and "
                "no passphrase or key."
            )

    @utils.config_restore("duplicity")
    def test_encryption_true_with_key(self):
        """Verify encryption with a valid gpg key."""
        zaza.model.set_application_config(
            self.application_name, dict(disable_encryption="False"), self.model_name
        )
        try:
            duplicity_workload_checker = utils.get_workload_application_status_checker(
                self.application_name, "blocked"
            )
            _run(zaza.model.async_block_until(duplicity_workload_checker, timeout=15))
        except concurrent.futures._base.TimeoutError:
            self.fail(
                "Failed to enter blocked state with encryption enables and "
                "no passphrase or key."
            )
        zaza.model.set_application_config(
            self.application_name, dict(gpg_public_key="S0M3k3Y")
        )
        try:
            zaza.model.block_until_all_units_idle()
        except concurrent.futures._base.TimeoutError:
            self.fail(
                "Not all units entered idle state. Config change back failed "
                "to achieve active/idle."
            )

    @utils.config_restore("duplicity")
    def test_encryption_true_with_passphrase(self):
        """Verify encryption with a valid passphrase."""
        zaza.model.set_application_config(
            self.application_name, dict(disable_encryption="False"), self.model_name
        )
        try:
            duplicity_workload_checker = utils.get_workload_application_status_checker(
                self.application_name, "blocked"
            )
            _run(zaza.model.async_block_until(duplicity_workload_checker, timeout=15))
        except concurrent.futures._base.TimeoutError:
            self.fail(
                "Failed to enter blocked state with encryption enables and "
                "no passphrase or key."
            )
        zaza.model.set_application_config(
            self.application_name, dict(encryption_passphrase="somephrase")
        )
        try:
            zaza.model.block_until_all_units_idle()
        except concurrent.futures._base.TimeoutError:
            self.fail(
                "Not all units entered idle state. Config change back "
                "failed to achieve active/idle."
            )


class DuplicityBackupCommandTest(BaseDuplicityTest):
    """Verify do-backup command."""

    @classmethod
    def setUpClass(cls):
        """Set up do-backup command tests."""
        super().setUpClass()
        cls.backup_host = zaza.model.get_units("backup-host")[0]
        cls.duplicity_unit = zaza.model.get_units("duplicity")[0]
        cls.backup_host_ip = cls.backup_host.public_address
        user_pass_pair = ubuntu_user_pass.split(":")
        cls.remote_user = user_pass_pair[0]
        cls.remote_pass = user_pass_pair[1]
        cls.action = "do-backup"
        cls.ssh_priv_key = cls.get_ssh_priv_key()

    def get_config(self, **kwargs):
        """Return app config."""
        base_config = dict(
            remote_backup_url=self.backup_host_ip,
            aux_backup_directory=ubuntu_backup_directory_source,
            remote_user=self.remote_user,
            remote_password=self.remote_pass,
        )
        for key, value in kwargs.items():
            base_config[key] = value
        return base_config

    @staticmethod
    def get_ssh_priv_key():
        """Return ssh private key."""
        with open("./tests/resources/testing_id_rsa", "rb") as f:
            ssh_private_key = f.read()
        encoded_ssh_private_key = base64.b64encode(ssh_private_key)
        return encoded_ssh_private_key.decode("utf-8")

    @utils.config_restore("duplicity")
    def test_scp_full_do_backup_action(self):
        """Verify do-backup action with scp."""
        additional_config = dict(backend="scp")
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_file_full_do_backup_action(self):
        """Verify do-backup action with ftp."""
        additional_config = dict(
            backend="file", remote_backup_url="/home/ubuntu/test-backups"
        )
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_scp_full_ssh_key_auth_backup_action(self):
        """Verify do-backup action with scp and private key."""
        additional_config = dict(
            backend="scp", private_ssh_key=self.ssh_priv_key, remote_password=""
        )
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_rsync_full_ssh_key_auth_backup_action(self):
        """Verify do-backup action with rsync and private key."""
        additional_config = dict(
            backend="rsync", private_ssh_key=self.ssh_priv_key, remote_password=""
        )
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_sftp_full_do_backup(self):
        """Verify do-backup action with sftp and password."""
        additional_config = dict(backend="sftp")
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_sftp_full_ssh_key_do_backup(self):
        """Verify do-backup action with sftp with private key."""
        additional_config = dict(
            backend="sftp", private_ssh_key=self.ssh_priv_key, remote_password=""
        )
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_ftp_full_do_backup(self):
        """Verify do-backup action with ftp."""
        additional_config = dict(backend="ftp")
        new_config = self.get_config(**additional_config)
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )


class DuplicityListFilesCommandTest(BaseDuplicityTest):
    """Verify list-current-files action."""

    @classmethod
    def setUpClass(cls):
        """Set up list-current-files action tests."""
        super().setUpClass()
        cls.backup_host = zaza.model.get_units("backup-host")[0]
        cls.duplicity_unit = zaza.model.get_units("duplicity")[0]
        cls.backup_host_ip = cls.backup_host.public_address
        user_pass_pair = ubuntu_user_pass.split(":")
        cls.remote_user = user_pass_pair[0]
        cls.remote_pass = user_pass_pair[1]
        cls.action = "list-current-files"
        cls.ssh_priv_key = cls.get_ssh_priv_key()

    def get_config(self, **kwargs):
        """Get charm config."""
        base_config = dict(
            remote_backup_url=self.backup_host_ip,
            aux_backup_directory=ubuntu_backup_directory_source,
            remote_user=self.remote_user,
            remote_password=self.remote_pass,
        )
        base_config.update(kwargs)
        return base_config

    @staticmethod
    def get_ssh_priv_key():
        """Get ssh private key."""
        with open("./tests/resources/testing_id_rsa", "rb") as f:
            ssh_private_key = f.read()
        encoded_ssh_private_key = base64.b64encode(ssh_private_key)
        return encoded_ssh_private_key.decode("utf-8")

    @utils.config_restore("duplicity")
    def test_scp_full_list_current_files_action(self):
        """Verify list-current-files work with scp backend."""
        new_config = self.get_config(backend="scp")
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_file_full_list_current_files_action(self):
        """Verify list-current-files work with file backend."""
        new_config = self.get_config(
            backend="file", remote_backup_url="/home/ubuntu/test-backups"
        )
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_scp_full_ssh_key_auth_list_current_files_action(self):
        """Verify list-current-files work after do-backup run."""
        new_config = self.get_config(
            backend="scp", private_ssh_key=self.ssh_priv_key, remote_password=""
        )
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_rsync_full_ssh_key_auth_list_current_files_action(self):
        """Verify list-current-files work with rsync backend after do-backup run."""
        new_config = self.get_config(
            backend="rsync", private_ssh_key=self.ssh_priv_key, remote_password=""
        )
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_sftp_full_list_current_files(self):
        """Verify list-current-files work with sftp backend after do-backup run."""
        new_config = self.get_config(backend="sftp")
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_sftp_full_ssh_key_list_current_files(self):
        """Verify list-current-files work with sftp backend after do-backup run."""
        new_config = self.get_config(
            backend="sftp", private_ssh_key=self.ssh_priv_key, remote_password=""
        )
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )

    @utils.config_restore("duplicity")
    def test_ftp_full_list_current_files(self):
        """Verify list-current-files work with ftp backend after do-backup run."""
        new_config = self.get_config(backend="ftp")
        utils.set_config_and_wait(self.application_name, new_config)
        zaza.model.run_action(
            self.duplicity_unit.name, "do-backup", raise_on_failure=True
        )
        zaza.model.run_action(
            self.duplicity_unit.name, self.action, raise_on_failure=True
        )
