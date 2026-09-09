# 认证模块（Authentication）

## 功能职责

认证模块负责建立和维护用户身份，让用户能够安全地进入、使用和退出个人知识库。

- 用户注册和账户创建。
- 用户登录和凭证签发。
- 当前用户身份解析。
- 忘记密码、一次性重置凭证和密码重置。
- 注销当前登录会话。
- 向其他模块提供当前用户身份，不替其他模块判断资源业务权限。

## 边界

- 只负责账户身份、密码凭证和登录会话，不负责文档内容、知识检索或问答生成。
- 用户能否访问某条文档或某个会话，由对应业务模块结合当前用户身份判断；auth 不拥有这些资源。
- 忘记密码只负责生成、校验和失效一次性重置凭证，不负责邮件或短信服务本身。
- 注销只撤销当前登录凭证，不删除用户已经保存的文档、专题和会话数据。
- 密码只能保存不可逆摘要，任何接口都不能返回原始密码或密码摘要。

## 内部拆分

### 用户注册（Registration）

用户注册负责校验邮箱、创建用户和保存密码摘要；不负责创建登录会话，也不负责发送重置通知。

~~~go
type User struct {
    ID string
    Email string
    PasswordHash string
    Status UserStatus // active、disabled。
    CreatedAt time.Time
}

type RegisterInput struct {
    Email string
    Password string
}

type Registration interface {
    Register(input RegisterInput) (User, error) // 校验注册信息并创建用户。
    FindByEmail(email string) (User, error) // 根据邮箱查找用户，供注册和登录检查使用。
}
~~~

### 登录会话（Login Session）

登录会话负责校验密码、签发凭证、解析当前用户和撤销凭证；不负责修改用户资料或访问业务资源。

~~~go
type LoginInput struct {
    Email string
    Password string
}

type AuthToken struct {
    AccessToken string
    ExpiresAt time.Time
}

type LoginSession interface {
    Login(input LoginInput) (AuthToken, User, error) // 校验密码并签发登录凭证。
    CurrentUser(accessToken string) (User, error) // 解析凭证并返回当前用户。
    Logout(accessToken string) error // 撤销当前登录凭证。
}
~~~

### 密码恢复（Password Recovery）

密码恢复负责创建、校验和消费一次性重置凭证；不负责直接暴露用户是否存在，也不负责通知渠道的具体实现。

~~~go
type PasswordResetRequest struct {
    Email string
}

type PasswordResetToken struct {
    TokenHash string
    UserID string
    ExpiresAt time.Time
    UsedAt *time.Time
}

type PasswordRecovery interface {
    RequestReset(input PasswordResetRequest) error // 创建短时有效的重置凭证并交给通知适配层。
    ResetPassword(token string, newPassword string) error // 校验一次性凭证并更新密码摘要。
}
~~~

### 身份依赖（Identity Context）

身份依赖负责把请求凭证解析成当前用户；不负责判断文档、会话或专题是否属于该用户。

~~~go
type IdentityContext struct {
    UserID string
    Email string
}

func RequireIdentity(accessToken string) (IdentityContext, error) // 校验请求凭证并返回当前用户身份。
~~~

## 流程

用户先注册或登录，之后带着登录凭证访问其他领域；忘记密码时使用一次性凭证完成重置，注销时撤销当前凭证。

~~~text
// 注册
Registration.Register(...)
LoginSession.Login(...)

// 登录
Registration.FindByEmail(...)
LoginSession.Login(...)

// 访问业务接口
RequireIdentity(...)

// 忘记密码
PasswordRecovery.RequestReset(...)
PasswordRecovery.ResetPassword(...)

// 注销
LoginSession.Logout(...)
~~~
