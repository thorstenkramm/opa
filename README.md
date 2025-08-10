## opa

**O**ptimized **P**ercona-Xtrabackup **A**rchiver

Many wrappers around `percona XtraBackup` have been written. `OPA` is what fits best the requirements of
[dimedis GmbH](https://www.linkedin.com/company/dimedis).

Key features at a glance:

- Controlled by toml configuration file
- Built-in Zabbix reporting
- Deletion of old backups
- Comprehensive logging
- No pip required. All required packages included in Debian & Ubuntu
- Supervision of the XtraBackup process and control of final success message
- Option to run additional commands before and after the backup
- Distributed as a single-file Python zipap
- Prevention of running backups without sufficient disk space

Refer to the [example of the configuration file](./opa.conf.example):

## Installation

On Debian 11 and Ubuntu 20.04 install required python modules:

```bash
apt install python3-toml
```

Debian 12 and Ubuntu 24.04. come with a python 3.11+ which has toml support built-in.

Install:

```bash
cd /tmp
wget https://github.com/thorstenkramm/opa/releases/download/0.0.1/opa-0.0.1.tar.gz
tar xf opa-0.0.1.tar.gz
sudo mv opa.pyz /usr/local/bin/opa
sudo chmod +x /usr/local/bin/opa
sudo mkdir /etc/opa
sudo mv opa.conf.example /etc/opa/opa.conf
rm opa-0.0.1.tar.gz
```

If you are planning to store backups as single tar.gz files, it's highly recommended to install
[pigz - Parallel gzip](https://zlib.net/pigz/).

```bash
apt install pigz
```

## Backup strategies

OPA supports the following backup strategies:

1. **Regular**: The default backup created by XtraBackup. You get a uncompressed copy of all tables and transaction
   logs.
   This backup is not suitable to to start MySQL because the transaction log has not been written to the tables yet.
   The so-called prepare step is missing. A "regular" backup consumes the same disk space as your database. The backup
   consists of a folder with almost the same files as in the MySQL data directory.
2. **Regular+Prepare**: After tables and logs have been copied to the destination, the prepare job is run, resulting in a
   directory that can be used to start MySQL directly. The prepare job doesn't consume additional disk space. To restore a lost
   database, the XtraBackup utility is not required.
   Use `prepare = true` in the [opa.conf](./opa.conf.example).
3. **Streamcompress**: Xtrabackup will be run with the `--stream=xbstream` flag. The backup of all your databases will
   be packaged into a single file with the suffix `.xbstream`. It's similar to a tar file. Inside the package all files
   are individually compresses with qpress. The backup is not "prepared", that means you cannot start your database
   directly on the backup. As the backup is streamed to the target file, no extra disk or temporary space is required
   for additional preparation steps.  
   For a restore the XtraBackup and the
   [qpress utility](https://ftpmirror.your.org/pub/percona/pxc-80/apt/pool/main/q/qpress/) are required.  
   Use `streamcompress = true` in the [opa.conf](./opa.conf.example).

Optionally the folder created by the strategies 1 and 2 can be compressed into a single tar.gz file. Keep in mind, that
compressing into a single file requires additional disk space. Until the compressing is not entirely completed,
the hard drive must be able to hold both the uncompressed and compressed backup.  
Use `tgz = true` in the [opa.conf](./opa.conf.example).

## Run the backup

Edit `/etc/opa/opa.conf` to your needs. Then run `opa` from cron.

> [!IMPORTANT]
> You must run `opa` from a user account – such as root – that has read access to the mysql data directory.

Adding a user to the `mysql` user group is usually not sufficient because the mysql data directory hase mode 0700.

## Authentication

Percona Xtrabackup and opa uses the mysql client executable installed to your system. These command line utilities will
read
all mysql configuration files as configured for your database installation. If you need authentication to backup your
database you can for example create a file `~/.my.cnf` and put the password for accessing the database there.  
Alternatively you can setup passwordless access via the authentication socket. The latter is since MySQL 8.X the default
on most installations.

## Conditions

Conditions are commands that are executed before and after the backup. You can hook in your commands at three different
phases of the backup process.

- `skip_conditions`, with this list of commands you can intentionally skip a backup but it's logged as successfully.
  This is useful to dynamically react on role changes in a cluster.
- `run_conditions`, with this list of commands you can asure all conditions are met to run the backup. If a run
  condition is not met, an error is logged and the backup is aborted and considered faulty. This is useful to mount
  or verify storage devices.
- `terminate_conditions`, this list of commands is run after the XtraBackup backup and all storage cleanup routines
  have terminated. If command from the terminate conditions fail (exit code >0), an error is logged and the backup
  is considered faulty. This is useful to copy the backup to remote locations.

Refer to the [example of the configuration file](./opa.conf.example) for more details and all options.

When running opa in debug logging mode, stdout of the condition command is written to the opa log.
In info logging mode, only the exit code of commands is logged. Errors (stderr) are always logged. 