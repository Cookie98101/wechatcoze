var apiService = {
	refresh: function(time, id, mac) {
		return service({
			url: `/train/across/competition/refreshCircle?beginTime=${time}&groupId=${id}&macs=${mac}`,
			method: 'post'
		})
	},

	getUserInfoByGroupId(params) {
		return service({
			url: `/train/across/competition/groupUserInfoList`,
			method: 'get',
			params
		})
	},

}
