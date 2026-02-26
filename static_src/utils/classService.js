let service = () => { } // 临时变量，空函数，初始化后等于axios实例
class Service {
    constructor() {
        this.url = ''
        this.version = ''
        this.service = ''
        this.isDebug = true
    }

    setUrlInfo(url, version) {
        this.url = url
        this.version = version
        this.requestUrl()
        service = this.service
    }

    requestUrl() {

        this.service = axios.create({
            baseURL: this.url
        })

        this.service.interceptors.request.use(config => {
            config.headers['version'] = this.version;
            return config
        }, error => {
            return Promise.reject(error)
        })

        this.service.interceptors.response.use(response => {
            return response
        }, error => {
            const {
                status
            } = error.response
            if (status == 500) {
                Message.error('出现错误')
            }
            if (status == 429) {
                Message.error('请求频繁,网络延时')
                // router.push('/404')
            }
            if (status == 428) {
                Message.error('验证码错误')
                router.push('/login')
            }
            if (status == 426) {
                Message.error('用户名或密码错误')
                router.push('/login')
            }
            if (status == 401) {
                Message.error('您已被登出或登录超时')
                router.push('/login')
            }
            if (status == 400) {
                Message.error(error.response.data.msg)
            }

            return Promise.reject(error)
        })
    }
}