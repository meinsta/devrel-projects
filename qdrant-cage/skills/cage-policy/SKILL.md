# /cage-policy - manage execution policy

you are managing the cage execution policy (cage.rules).

## trigger

user runs `/cage-policy` to view, add, or modify execution rules.

## commands

### view current policy
```bash
cage policy
```

### add a blocked command
ask the user:
1. what command to block
2. what the sanctioned alternative is

then add to cage.rules:
```
block   <command>    <alternative>
```

### add a prompted command
ask the user:
1. what command should require confirmation

then add to cage.rules:
```
prompt  <command>
```

### validate
```bash
cage check policy
```

## rules

- never remove safety rules without explicit user confirmation
- always suggest a sanctioned alternative when blocking a command
- keep cage.rules sorted: blocks first, then prompts
