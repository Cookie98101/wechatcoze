Vue.component('todo-item', {
    // "prop"，类似于一个自定义 attribute。
    props: ['todo'],
    template: `<div><li class="todo_class">{{ todo.text }}</li>
    <button @click='clickBtn'>{{btn_tips}}</button>
    </div>`,
    data() {
        return {
            btn_tips: '我是Vue组件中的 message'
        }
    },
    created: function () {
        // 将python_call_js方法绑定到window下面，提供给python外部调用
        let that = this;
        // window['python_call_js'] = (url) => {
        //     return that.python_call_js(url)
        // }
    },
    methods: {
        python_call_js(url) {
            this.btn_tips = 'zzuuu_test_ok'
            return 'ok'
        },
        clickBtn() {
            apiService.ipquery().then((res) => {
                let resData = res.data
                alert(JSON.stringify(resData))
                if (resData.code == 0) {

                } else {
                    throw resData.msg
                }
            }).catch((error) => {

            })
        },
    }
})