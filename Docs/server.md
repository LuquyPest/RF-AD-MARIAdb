# Server install

# **Summary**
- [The Active Directory part](./server.md/#the-active-directory-part)
    - [1. Modify the LDAP Schema](./server.md/#1-modify-the-ldap-schema)  
    - [2. Create an LDAP User for Sync](./server.md/#2-create-an-ldap-user-for-sync)
- [The Linux Part](./server.md/#the-linux-part)
    - [3. Clone the Repository](./server.md/#3-clone-the-repository)
    - [4. fill env.py](./server.md/#4-fill-env.py)
    - [5. Run the system](./server.md/#5-run-system)

# The Active Directory part

## 1. Modify the LDAP Schema

To add the `rFIDUID` attribute to your LDAP schema, follow these steps:

### Open PowerShell as Administrator

1. **Open PowerShell as Administrator**: This is required to make changes to the LDAP schema.

### Add the `rFIDUID` Attribute

2. **Add the `rFIDUID` Attribute**: Use the following PowerShell commands to add the `rFIDUID` attribute to the LDAP schema.

   ```powershell
   Import-Module ActiveDirectory

   # Define the new attribute
   $attribute = New-Object PSObject -Property @{
       lDAPDisplayName = "rFIDUID"
       adminDescription = "RFID UID"
       attributeSyntax = "2.5.5.12"
       oMSyntax = 64
       isSingleValued = $true
   }

   # Add the new attribute to the schema
   New-ADObject -Name "rFIDUID" -Type "attributeSchema" -OtherAttributes $attribute

3. **Add the Attribute to a Class**: Update the user class to include the `rFIDUID` attribute.
    ```powershell
    # Find the user class
    $userClass = Get-ADObject -LDAPFilter "(cn=user)" -SearchBase "CN=Schema,CN=Configuration,DC=your-domain,DC=com" -SearchScope Base

    # Add the new attribute to the user class
    Set-ADObject -Identity $userClass -Add @{mayContain="rFIDUID"}
    ```

## 2. Create an LDAP User for Sync
Create a dedicated LDAP user for synchronizing data:  
⚠️ Do not forget to replace the domain by yours and the password by a strong one.
```powershell
    New-ADUser -Name "RO.RF-AD" ` #You can change this if you want 
        -GivenName "ReadOnly" `
        -Surname "AD" `
        -UserPrincipalName "RO.RF-AD@your-domain.com" `
        -Path "OU=Users,DC=your-domain,DC=com" `
        -AccountPassword (ConvertTo-SecureString -AsPlainText "[YOUR PASSWORD]" -Force) `
        -Enabled $true

    # Grant read permissions
    $ldapUser = Get-ADUser -Identity "RO.RF-AD"
    Add-ADPermission -Identity "OU=Users,DC=your-domain,DC=com" -User $ldapUser -AccessRights ReadProperty
```

# The Linux Part

For this part you'll need linux, you can frollow this tutorial to install it proprely  
➡️ [Gude for install ubuntu server](https://www.zdnet.com/article/how-to-install-ubuntu-server-in-under-30-minutes/)  
⚠️ I cannot guarantee the accuracy of the information contained in this guide. ⚠️
## 3. Clone the Repository

```bash
git clone https://github.com/jeanGaston/RF-AD.git
```
Then navigate into the server folder
```bash
cd ./RD-AD/Server
```
## 4. Fill env.py

Open env.py file in the [server directory](../Server/) with the following content:
    Replace AD-password / ip-AD :

```
LDAPUSER = "RF-AD\RO.RF-AD"
LDAPPASS = "AD-password"
LDAP_SERVER = "ldap://ip-AD"
DOOR_ACCESS_GROUPS_DN = "OU=DOORS,DC=RF-AD,DC=com"
USERS_DN = "OU=UTILISATEURS,DC=RF-AD,DC=com"
WebServerPORT = 5000
DBFILE = {
    "host": "localhost",
    "user": "root",
    "password": "Password",
    "database": "controle_acces"
}
```
⚠️ **IF YOU CHANGE THE WEB SERVER PORT** ⚠️  
You'll need to change it in the [reader code](../Client/main.py)

## 5. Run system

Execute this code for the first time
```bash
sudo ./install.sh 
```

Execute this code for the other time 
```bash
sudo python3 server.py
```
And after this you can connect with web-brownser with https://"ip-linux":5000