; Instalador de Alcalde Digital para Windows (Inno Setup 6). Instala la carpeta onedir de PyInstaller SIN permisos de
; administrador, en %LOCALAPPDATA%\Programs\AlcaldeDigital. Sin telemetria: Inno Setup no envia nada y este script tampoco.
; SIN PROBAR en Windows real (se escribio en macOS). Lo compila el workflow .github/workflows/construir-ejecutables.yml:
;   ISCC.exe /DOrigen=<dist\AlcaldeDigital> /DSalida=<carpeta> /DVersion=<x.y.z> empaquetado\instalador_windows.iss
#ifndef Origen
  #error Falta /DOrigen=<carpeta dist\AlcaldeDigital de PyInstaller (onedir)>
#endif
#ifndef Salida
  #define Salida "salida"
#endif
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
; AppId fijo: permite que una version nueva actualice sobre la anterior y que el desinstalador la encuentre. No cambiar.
AppId={{7D3F5C1A-2B64-4E0A-9C58-A1C0DE5E0001}
AppName=Alcalde Digital
AppVersion={#Version}
AppPublisher=Alcalde Digital (proyecto de aprendizaje)
DefaultDirName={autopf}\AlcaldeDigital
DefaultGroupName=Alcalde Digital
; Sin administrador: {autopf} pasa a ser %LOCALAPPDATA%\Programs y los accesos van al menu Inicio del usuario.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
; Pagina de aviso: resumen legal con enlaces a los documentos (se muestra antes de instalar).
InfoBeforeFile=AVISO_INSTALADOR.txt
UninstallDisplayName=Alcalde Digital
UninstallDisplayIcon={app}\AlcaldeDigital.exe
OutputDir={#Salida}
OutputBaseFilename=AlcaldeDigital-Setup-Windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Sin firma digital (no hay certificado): Windows SmartScreen avisara; la web lo explica y publica el SHA-256.

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "iconoescritorio"; Description: "Crear un acceso directo en el &Escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Alcalde Digital"; Filename: "{app}\AlcaldeDigital.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Alcalde Digital"; Filename: "{app}\AlcaldeDigital.exe"; WorkingDir: "{app}"; Tasks: iconoescritorio

[Run]
Filename: "{app}\AlcaldeDigital.exe"; Description: "Abrir Alcalde Digital"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent unchecked

; Al desinstalar solo se borra lo que instalo este programa; las partidas guardadas (carpeta personal del usuario) se conservan.
