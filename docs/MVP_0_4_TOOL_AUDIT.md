# Ferramenta nativa opcional — revisão antes da execução

17/11/2026. `tools/vision_people.swift` é código próprio revisado antes de compilar:
leitura de imagens somente sob o diretório do projeto após resolver symlinks;
Vision human rectangles; JSON em stdout. Não possui shell, instalação, rede,
identificação de pessoas, persistência ou download de modelo.

Compilador existente em Xcode.app: assinatura `com.apple.swift-frontend`, equipe
Apple `59GAB85EFG`, verificada com `codesign --verify --strict`. Hash do compilador
e do fonte revisado em `workspace/director-0.4/tool-audit.json`. Compilação, módulos
e temporários ficam no projeto. Não se afirma auditoria interna do framework Apple.
O helper será executado sob sandbox negando rede, com hashes verificados pelo
wrapper. Falhas não autorizam baixar nada nem contornar o sandbox.

Fontes oficiais:
- https://developer.apple.com/documentation/vision/vndetecthumanrectanglesrequest
- https://developer.apple.com/documentation/vision/vndetecthumanrectanglesrequest/upperbodyonly
- https://developer.apple.com/documentation/professional-video-applications/adjust-transform
- https://developer.apple.com/documentation/professional-video-applications/adjustment-attributes-and-effect-parameters

Caixas são evidência de detecção, não identidade ou confirmação do sujeito
principal. Reframing exige consistência temporal; ausência ou conflito gera crop
central e revisão manual. Sem inferência de direção do olhar a partir de caixas.
