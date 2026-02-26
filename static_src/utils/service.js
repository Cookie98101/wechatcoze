// 是否debugger模式
var isDebug = true;
var baseURL = '';
var version='';
if (isDebug) {
	baseURL = 'http://49.81.98.22:19999'
	version = 'jyx'
} else {
	baseURL = 'http://114.115.169.3:9999'
//	baseURL = 'http://127.0.0.1:9999'
	version = 'mh'
}
const service = axios.create({
	baseURL: baseURL
})

service.interceptors.request.use(config => {
	config.headers['version'] = version;
	return config
}, error => {
	return Promise.reject(error)
})

service.interceptors.response.use(response => {
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