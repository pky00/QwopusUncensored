# QwopusUncensored

Self-hosted uncensored 27B coding agent on AWS. See [plan.md](plan.md) for full architecture and deployment guide.

## SSH Access

SSH is only needed for initial server setup and occasional maintenance. The security group restricts port 22 to your current IP address, which means you need to update it whenever your home IP changes.

### Check your current IP

```bash
curl -s https://checkip.amazonaws.com
```

### Update the SSH rule

1. Remove the old rule (replace `OLD_IP` with the IP currently in the SG):

```bash
aws ec2 revoke-security-group-ingress --region eu-west-1 \
  --group-id sg-0b7ae8f721b3e494d \
  --protocol tcp --port 22 --cidr OLD_IP/32
```

2. Add your new IP:

```bash
aws ec2 authorize-security-group-ingress --region eu-west-1 \
  --group-id sg-0b7ae8f721b3e494d \
  --protocol tcp --port 22 --cidr $(curl -s https://checkip.amazonaws.com)/32
```

### One-liner (revoke old + add new)

```bash
# Find the current allowed IP
aws ec2 describe-security-groups --region eu-west-1 \
  --group-ids sg-0b7ae8f721b3e494d \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\`].IpRanges[0].CidrIp" \
  --output text

# Then revoke it and add your current IP
OLD_IP=$(aws ec2 describe-security-groups --region eu-west-1 \
  --group-ids sg-0b7ae8f721b3e494d \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\`].IpRanges[0].CidrIp" \
  --output text) && \
aws ec2 revoke-security-group-ingress --region eu-west-1 \
  --group-id sg-0b7ae8f721b3e494d \
  --protocol tcp --port 22 --cidr $OLD_IP && \
aws ec2 authorize-security-group-ingress --region eu-west-1 \
  --group-id sg-0b7ae8f721b3e494d \
  --protocol tcp --port 22 --cidr $(curl -s https://checkip.amazonaws.com)/32
```

### Connect

```bash
ssh -i ~/.ssh/qwopus-key.pem ubuntu@34.251.74.30
```
